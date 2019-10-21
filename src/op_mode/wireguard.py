#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#

import argparse
import os
import sys
import shutil
import subprocess
import syslog as sl
import re
import time


from vyos import ConfigError
from vyos.config import Config

dir = r'/config/auth/wireguard'
psk = dir + '/preshared.key'

def check_kmod():
    """ check if kmod is loaded, if not load it """
    if not os.path.exists('/sys/module/wireguard'):
        sl.syslog(sl.LOG_NOTICE, "loading wirguard kmod")
        if os.system('sudo modprobe wireguard') != 0:
            sl.syslog(sl.LOG_ERR, "modprobe wireguard failed")
            raise ConfigError("modprobe wireguard failed")


def showint(interface):
    output = subprocess.check_output(["wg", "show", interface], universal_newlines=True)
    c = Config()
    c.set_level("interfaces wireguard {}".format(interface))
    description = c.return_effective_value("description".format(interface))
    """ if the interface has a description, modify the output to include it """
    if (description):
        output = re.sub(r"interface: {}".format(re.escape(interface)),"interface: {}\n  Description: {}".format(interface,description),output)
    
    """ pull the last handshake times.  Assume if the handshake was greater than 5 minutes, the tunnel is down """
    peer_timeouts = {}
    last_hs_output = subprocess.check_output(["wg", "show", interface, "latest-handshakes"], universal_newlines=True)
    for match in re.findall(r'(\S+)\s+(\d+)',last_hs_output): 
        peer_timeouts[match[0]] = match[1]

    """ modify all the peers, reformat to provide VyOS config provided peername, whether the tunnel is up/down """
    for peer in c.list_effective_nodes(' peer'):
        pubkey = c.return_effective_value("peer {} pubkey".format(peer))
        status = ""
        if int(peer_timeouts[pubkey]) > 0:
            #Five minutes and the tunnel is still up
            if (time.time() - int(peer_timeouts[pubkey]) < (60*5)):
                status = "UP"
            else:
                status = "DOWN"
        elif (peer_timeouts[pubkey] is None):
            status = "DOWN"
        elif (int(peer_timeouts[pubkey]) == 0):
            status = "DOWN"

        output = re.sub(r"peer: {}".format(re.escape(pubkey)),"peer: {}\n  Status: {}\n  public key: {}".format(peer,status,pubkey),output)

    print(output)
    
def generate_keypair(pk, pub):
    """ generates a keypair which is stored in /config/auth/wireguard """
    old_umask = os.umask(0o027)
    ret = subprocess.call(
        ['wg genkey | tee ' + pk + '|wg pubkey > ' + pub], shell=True)
    if ret != 0:
        raise ConfigError("wireguard key-pair generation failed")
    else:
        sl.syslog(
            sl.LOG_NOTICE, "new keypair wireguard key generated in " + dir)
    os.umask(old_umask)


def genkey(location):
    """ helper function to check, regenerate the keypair """
    pk = "{}/private.key".format(location)
    pub = "{}/public.key".format(location)
    old_umask = os.umask(0o027)
    if os.path.exists(pk) and os.path.exists(pub):
        try:
            choice = input(
                "You already have a wireguard key-pair, do you want to re-generate? [y/n] ")
            if choice == 'y' or choice == 'Y':
                generate_keypair(pk, pub)
        except KeyboardInterrupt:
            sys.exit(0)
    else:
        """ if keypair is bing executed from a running iso """
        if not os.path.exists(location):
            subprocess.call(['sudo mkdir -p ' + location], shell=True)
            subprocess.call(['sudo chgrp vyattacfg ' + location], shell=True)
            subprocess.call(['sudo chmod 750 ' + location], shell=True)
        generate_keypair(pk, pub)
    os.umask(old_umask)


def showkey(key):
    """ helper function to show privkey or pubkey """
    if os.path.exists(key):
        print (open(key).read().strip())
    else:
        print ("{} not found".format(key))


def genpsk():
    """
        generates a preshared key and shows it on stdout,
        it's stored only in the cli config
    """

    subprocess.call(['wg genpsk'], shell=True)

def list_key_dirs():
    """ lists all dirs under /config/auth/wireguard """ 
    if os.path.exists(dir):
        nks = next(os.walk(dir))[1]
        for nk in nks:
            print (nk)

def del_key_dir(kname):
    """ deletes /config/auth/wireguard/<kname> """
    kdir = "{0}/{1}".format(dir,kname)
    if not os.path.isdir(kdir):
        print ("named keypair {} not found".format(kname))
        return 1
    shutil.rmtree(kdir)


if __name__ == '__main__':
    check_kmod()
    parser = argparse.ArgumentParser(description='wireguard key management')
    parser.add_argument(
        '--genkey', action="store_true", help='generate key-pair')
    parser.add_argument(
        '--showpub', action="store_true", help='shows public key')
    parser.add_argument(
        '--showpriv', action="store_true", help='shows private key')
    parser.add_argument(
        '--genpsk', action="store_true", help='generates preshared-key')
    parser.add_argument(
        '--location', action="store", help='key location within {}'.format(dir))
    parser.add_argument(
        '--listkdir', action="store_true", help='lists named keydirectories')
    parser.add_argument(
        '--delkdir', action="store_true", help='removes named keydirectories')
    parser.add_argument(
        '--showinterface', action="store", help='shows interface details')
    args = parser.parse_args()

    try:
        if args.genkey:
            if args.location:
                genkey("{0}/{1}".format(dir, args.location))
            else:
                genkey("{}/default".format(dir))
        if args.showpub:
            if args.location:
                showkey("{0}/{1}/public.key".format(dir, args.location))
            else:
                showkey("{}/default/public.key".format(dir))
        if args.showpriv:
            if args.location:
                showkey("{0}/{1}/private.key".format(dir, args.location))
            else:
                showkey("{}/default/private.key".format(dir))
        if args.genpsk:
            genpsk()
        if args.listkdir:
            list_key_dirs()
        if args.showinterface:
            showint(args.showinterface)
        if args.delkdir:
            if args.location:
                del_key_dir(args.location)
            else:
                del_key_dir("default")

    except ConfigError as e:
        print(e)
        sys.exit(1)
