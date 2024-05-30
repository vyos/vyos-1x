#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
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

import argparse

from sys import exit
from socket import getfqdn
from cryptography.x509.oid import NameOID

from vyos.configquery import ConfigTreeQuery
from vyos.pki import load_certificate
from vyos.template import render_to_string
from vyos.utils.io import ask_input

# Apple profiles only support one IKE/ESP encryption cipher and hash, whereas
# VyOS comes with a multitude of different proposals for a connection.
#
# We take all available proposals from the VyOS CLI and ask the user which one
# he would like to get enabled in his profile - thus there is limited possibility
# to select a proposal that is not supported on the connection profile.
#
# IOS supports IKE-SA encryption algorithms:
# - DES
# - 3DES
# - AES-128
# - AES-256
# - AES-128-GCM
# - AES-256-GCM
# - ChaCha20Poly1305
#
vyos2apple_cipher = {
    '3des'  : '3DES',
    'aes128' : 'AES-128',
    'aes256' : 'AES-256',
    'aes128gcm128' : 'AES-128-GCM',
    'aes256gcm128' : 'AES-256-GCM',
    'chacha20poly1305' : 'ChaCha20Poly1305',
}

# Windows supports IKE-SA encryption algorithms:
# - DES3
# - AES128
# - AES192
# - AES256
# - GCMAES128
# - GCMAES192
# - GCMAES256
#
vyos2windows_cipher = {
    '3des'  : 'DES3',
    'aes128' : 'AES128',
    'aes192' : 'AES192',
    'aes256' : 'AES256',
    'aes128gcm128' : 'GCMAES128',
    'aes192gcm128' : 'GCMAES192',
    'aes256gcm128' : 'GCMAES256',
}

# IOS supports IKE-SA integrity algorithms:
# - SHA1-96
# - SHA1-160
# - SHA2-256
# - SHA2-384
# - SHA2-512
#
vyos2apple_integrity = {
    'sha1'     : 'SHA1-96',
    'sha1_160' : 'SHA1-160',
    'sha256'   : 'SHA2-256',
    'sha384'   : 'SHA2-384',
    'sha512'   : 'SHA2-512',
}

# Windows supports IKE-SA integrity algorithms:
# - SHA1-96
# - SHA1-160
# - SHA2-256
# - SHA2-384
# - SHA2-512
#
vyos2windows_integrity = {
    'sha1'       : 'SHA196',
    'sha256'     : 'SHA256',
    'aes128gmac' : 'GCMAES128',
    'aes192gmac' : 'GCMAES192',
    'aes256gmac' : 'GCMAES256',
}

# IOS 14.2 and later do no support dh-group 1,2 and 5. Supported DH groups would
# be: 14, 15, 16, 17, 18, 19, 20, 21, 31
ios_supported_dh_groups = ['14', '15', '16', '17', '18', '19', '20', '21', '31']
# Windows 10 only allows a limited set of DH groups
windows_supported_dh_groups = ['1', '2', '14', '24']

parser = argparse.ArgumentParser()
parser.add_argument('--os', const='all', nargs='?', choices=['ios', 'windows'], help='Operating system used for config generation', required=True)
parser.add_argument("--connection", action="store", help='IPsec IKEv2 remote-access connection name from CLI', required=True)
parser.add_argument("--remote", action="store", help='VPN connection remote-address where the client will connect to', required=True)
parser.add_argument("--profile", action="store", help='IKEv2 profile name used in the profile list on the device')
parser.add_argument("--name", action="store", help='VPN connection name as seen in the VPN application later')
args = parser.parse_args()

ipsec_base = ['vpn', 'ipsec']
config_base = ipsec_base +  ['remote-access', 'connection']
pki_base = ['pki']
conf = ConfigTreeQuery()
if not conf.exists(config_base):
    exit('IPsec remote-access is not configured!')

profile_name = 'VyOS IKEv2 Profile'
if args.profile:
    profile_name = args.profile

vpn_name = 'VyOS IKEv2 VPN'
if args.name:
    vpn_name = args.name

conn_base = config_base + [args.connection]
if not conf.exists(conn_base):
     exit(f'IPsec remote-access connection "{args.connection}" does not exist!')

data = conf.get_config_dict(conn_base, key_mangling=('-', '_'),
                            get_first_key=True, no_tag_node_value_mangle=True)

data['profile_name'] = profile_name
data['vpn_name'] = vpn_name
data['remote'] = args.remote
# This is a reverse-DNS style unique identifier used to detect duplicate profiles
tmp = getfqdn().split('.')
tmp = reversed(tmp)
data['rfqdn'] = '.'.join(tmp)

pki = conf.get_config_dict(pki_base, get_first_key=True)
cert_name = data['authentication']['x509']['certificate']

data['certs'] = []

for ca_name in data['authentication']['x509']['ca_certificate']:
    tmp = {}
    ca_cert = load_certificate(pki['ca'][ca_name]['certificate'])
    cert = load_certificate(pki['certificate'][cert_name]['certificate'])


    tmp['ca_cn'] = ca_cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    tmp['cert_cn'] = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    tmp['ca_cert'] = conf.value(pki_base + ['ca', ca_name, 'certificate'])

    data['certs'].append(tmp)


esp_proposals = conf.get_config_dict(ipsec_base + ['esp-group', data['esp_group'], 'proposal'],
                                     key_mangling=('-', '_'), get_first_key=True)
ike_proposal = conf.get_config_dict(ipsec_base + ['ike-group', data['ike_group'], 'proposal'],
                                    key_mangling=('-', '_'), get_first_key=True)


# This script works only for Apple iOS/iPadOS and Windows. Both operating systems
# have different limitations thus we load the limitations based on the operating
# system used.

vyos2client_cipher = vyos2apple_cipher if args.os == 'ios' else vyos2windows_cipher;
vyos2client_integrity = vyos2apple_integrity if args.os == 'ios' else vyos2windows_integrity;
supported_dh_groups = ios_supported_dh_groups if args.os == 'ios' else windows_supported_dh_groups;

# Create a dictionary containing client conform IKE settings
ike = {}
count = 1
for _, proposal in ike_proposal.items():
    if {'dh_group', 'encryption', 'hash'} <= set(proposal):
        if (proposal['encryption'] in set(vyos2client_cipher) and
            proposal['hash'] in set(vyos2client_integrity) and
            proposal['dh_group'] in set(supported_dh_groups)):

            # We 're-code' from the VyOS IPsec proposals to the Apple naming scheme
            proposal['encryption'] = vyos2client_cipher[ proposal['encryption'] ]
            proposal['hash'] = vyos2client_integrity[ proposal['hash'] ]

            ike.update( { str(count) : proposal } )
            count += 1

# Create a dictionary containing Apple conform ESP settings
esp = {}
count = 1
for _, proposal in esp_proposals.items():
    if {'encryption', 'hash'} <= set(proposal):
        if proposal['encryption'] in set(vyos2client_cipher) and proposal['hash'] in set(vyos2client_integrity):
            # We 're-code' from the VyOS IPsec proposals to the Apple naming scheme
            proposal['encryption'] = vyos2client_cipher[ proposal['encryption'] ]
            proposal['hash'] = vyos2client_integrity[ proposal['hash'] ]

            esp.update( { str(count) : proposal } )
            count += 1
try:
    if len(ike) > 1:
        # Propare the input questions for the user
        tmp = '\n'
        for number, options in ike.items():
            tmp += f'({number}) Encryption {options["encryption"]}, Integrity {options["hash"]}, DH group {options["dh_group"]}\n'
        tmp += '\nSelect one of the above IKE groups: '
        data['ike_encryption'] = ike[ ask_input(tmp, valid_responses=list(ike)) ]
    else:
        data['ike_encryption'] = ike['1']

    if len(esp) > 1:
        tmp = '\n'
        for number, options in esp.items():
            tmp += f'({number}) Encryption {options["encryption"]}, Integrity {options["hash"]}\n'
        tmp += '\nSelect one of the above ESP groups: '
        data['esp_encryption'] = esp[ ask_input(tmp, valid_responses=list(esp)) ]
    else:
        data['esp_encryption'] = esp['1']

except KeyboardInterrupt:
    exit("Interrupted")

print('\n\n==== <snip> ====')
if args.os == 'ios':
    print(render_to_string('ipsec/ios_profile.j2', data))
    print('==== </snip> ====\n')
    print('Save the XML from above to a new file named "vyos.mobileconfig" and E-Mail it to your phone.')
elif args.os == 'windows':
    print(render_to_string('ipsec/windows_profile.j2', data))
    print('==== </snip> ====\n')
