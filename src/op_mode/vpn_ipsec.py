#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import base64
import os
import re
import struct
import sys
import argparse
from subprocess import TimeoutExpired

from vyos.util import ask_yes_no, call, cmd, process_named_running
from Crypto.PublicKey.RSA import importKey

RSA_LOCAL_KEY_PATH = '/config/ipsec.d/rsa-keys/localhost.key'
RSA_LOCAL_PUB_PATH = '/etc/ipsec.d/certs/localhost.pub'
RSA_KEY_PATHS = ['/config/auth', '/config/ipsec.d/rsa-keys']

X509_CONFIG_PATH = '/etc/ipsec.d/key-pair.template'
X509_PATH = '/config/auth/'

IPSEC_CONF = '/etc/ipsec.conf'
SWANCTL_CONF = '/etc/swanctl/swanctl.conf'

def migrate_to_vyatta_key(path):
    with open(path, 'r') as f:
        key = importKey(f.read())
        e = key.e.to_bytes((key.e.bit_length() + 7) // 8, 'big')
        n = key.n.to_bytes((key.n.bit_length() + 7) // 8, 'big')
        return '0s' + str(base64.b64encode(struct.pack('B', len(e)) + e + n), 'ascii')
    return None

def find_rsa_keys():
    keys = []
    for path in RSA_KEY_PATHS:
        if not os.path.exists(path):
            continue
        for filename in os.listdir(path):
            full_path = os.path.join(path, filename)
            if os.path.isfile(full_path) and full_path.endswith(".key"):
                keys.append(full_path)
    return keys

def show_rsa_keys():
    for key_path in find_rsa_keys():
        print('Private key: ' + os.path.basename(key_path))
        print('Public key: ' + migrate_to_vyatta_key(key_path) + '\n')

def generate_rsa_key(bits = 2192):
    if (bits < 16 or bits > 4096) or bits % 16 != 0:
        print('Invalid bit length')
        return

    if os.path.exists(RSA_LOCAL_KEY_PATH):
        if not ask_yes_no("A local RSA key file already exists and will be overwritten. Continue?"):
            return

    print(f'Generating rsa-key to {RSA_LOCAL_KEY_PATH}')

    directory = os.path.dirname(RSA_LOCAL_KEY_PATH)
    call(f'sudo mkdir -p {directory}')
    result = call(f'sudo /usr/bin/openssl genrsa -out {RSA_LOCAL_KEY_PATH} {bits}')

    if result != 0:
        print(f'Could not generate RSA key: {result}')
        return

    call(f'sudo /usr/bin/openssl rsa -inform PEM -in {RSA_LOCAL_KEY_PATH} -pubout -out {RSA_LOCAL_PUB_PATH}')

    print('Your new local RSA key has been generated')
    print('The public portion of the key is:\n')
    print(migrate_to_vyatta_key(RSA_LOCAL_KEY_PATH))

def generate_x509_pair(name):
    if os.path.exists(X509_PATH + name):
        if not ask_yes_no("A certificate request with this name already exists and will be overwritten. Continue?"):
            return

    result = os.system(f'openssl req -new -nodes -keyout {X509_PATH}{name}.key -out {X509_PATH}{name}.csr -config {X509_CONFIG_PATH}')
    
    if result != 0:
        print(f'Could not generate x509 key-pair: {result}')
        return

    print('Private key and certificate request has been generated')
    print(f'CSR: {X509_PATH}{name}.csr')
    print(f'Private key: {X509_PATH}{name}.key')

def get_peer_connections(peer, tunnel, return_all = False):
    search = rf'^[\s]*(peer_{peer}_(tunnel_[\d]+|vti)).*'
    matches = []
    with open(SWANCTL_CONF, 'r') as f:
        for line in f.readlines():
            result = re.match(search, line)
            if result:
                suffix = f'tunnel_{tunnel}' if tunnel.isnumeric() else tunnel
                if return_all or (result[2] == suffix):
                    matches.append(result[1])
    return matches

def reset_peer(peer, tunnel):
    if not peer:
        print('Invalid peer, aborting')
        return

    conns = get_peer_connections(peer, tunnel, return_all = (not tunnel or tunnel == 'all'))

    if not conns:
        print('Tunnel(s) not found, aborting')
        return

    result = True
    for conn in conns:
        try:
            call(f'sudo /usr/sbin/ipsec down {conn}', timeout = 10)
            call(f'sudo /usr/sbin/ipsec up {conn}', timeout = 10)
        except TimeoutExpired as e:
            print(f'Timed out while resetting {conn}')
            result = False


    print('Peer reset result: ' + ('success' if result else 'failed'))

def get_profile_connection(profile, tunnel = None):
    search = rf'(dmvpn-{profile}-[\w]+)' if tunnel == 'all' else rf'(dmvpn-{profile}-{tunnel})'
    with open(SWANCTL_CONF, 'r') as f:
        for line in f.readlines():
            result = re.search(search, line)
            if result:
                return result[1]
    return None

def reset_profile(profile, tunnel):
    if not profile:
        print('Invalid profile, aborting')
        return

    if not tunnel:
        print('Invalid tunnel, aborting')
        return

    conn = get_profile_connection(profile)

    if not conn:
        print('Profile not found, aborting')
        return

    call(f'sudo /usr/sbin/ipsec down {conn}')
    result = call(f'sudo /usr/sbin/ipsec up {conn}')

    print('Profile reset result: ' + ('success' if result == 0 else 'failed'))

def debug_peer(peer, tunnel):
    if not peer or peer == "all":
        call('sudo /usr/sbin/ipsec statusall')
        return

    if not tunnel or tunnel == 'all':
        tunnel = ''

    conn = get_peer_connections(peer, tunnel)

    if not conns:
        print('Peer not found, aborting')
        return

    for conn in conns:
        call(f'sudo /usr/sbin/ipsec statusall | grep {conn}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', help='Control action', required=True)
    parser.add_argument('--bits', help='Bits for rsa-key', required=False)
    parser.add_argument('--name', help='Name for x509 key-pair, peer for reset', required=False)
    parser.add_argument('--tunnel', help='Specific tunnel of peer', required=False)

    args = parser.parse_args()

    if args.action == 'rsa-key':
        bits = int(args.bits) if args.bits else 2192
        generate_rsa_key(bits)
    elif args.action == 'rsa-key-show':
        show_rsa_keys()
    elif args.action == 'x509':
        if not args.name:
            print('Invalid name for key-pair, aborting.')
            sys.exit(0)
        generate_x509_pair(args.name)
    elif args.action == 'reset-peer':
        reset_peer(args.name, args.tunnel)
    elif args.action == "reset-profile":
        reset_profile(args.name, args.tunnel)
    elif args.action == "vpn-debug":
        debug_peer(args.name, args.tunnel)
