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
from vyos.config import config_dict_mangle_acme
from vyos.pki import CERT_BEGIN
from vyos.pki import CERT_END
from vyos.pki import find_chain
from vyos.pki import encode_certificate
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
# be: 14, 15, 16, 17, 18, 19, 20, 21, 31, 32
vyos2apple_dh_group = {
    '14' : '14',
    '15' : '15',
    '16' : '16',
    '17' : '17',
    '18' : '18',
    '19' : '19',
    '20' : '20',
    '21' : '21',
    '31' : '31',
    '32' : '32'
}

# Newer versions of Windows support groups 19 and 20, albeit under a different naming convention
vyos2windows_dh_group = {
    '1'  : 'Group1',
    '2'  : 'Group2',
    '14' : 'Group14',
    '19' : 'ECP256',
    '20' : 'ECP384',
    '24' : 'Group24'
}

# For PFS, Windows also has its own inconsistent naming scheme for each group
vyos2windows_pfs_group = {
    '1'  : 'PFS1',
    '2'  : 'PFS2',
    '14' : 'PFS2048',
    '19' : 'ECP256',
    '20' : 'ECP384',
    '24' : 'PFS24'
}

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
if not conf.exists(pki_base):
    exit('PKI is not configured!')

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

if args.os == 'ios':
    pki = conf.get_config_dict(pki_base, get_first_key=True)
    if 'certificate' in pki:
        for certificate in pki['certificate']:
            pki['certificate'][certificate] = config_dict_mangle_acme(certificate, pki['certificate'][certificate])

    cert_name = data['authentication']['x509']['certificate']


    cert_data = load_certificate(pki['certificate'][cert_name]['certificate'])
    data['cert_common_name'] = cert_data.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    data['ca_common_name'] = cert_data.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    data['ca_certificates'] = []

    loaded_ca_certs = {load_certificate(c['certificate'])
        for c in pki['ca'].values()} if 'ca' in pki else {}

    for ca_name in data['authentication']['x509']['ca_certificate']:
        loaded_ca_cert = load_certificate(pki['ca'][ca_name]['certificate'])
        ca_full_chain = find_chain(loaded_ca_cert, loaded_ca_certs)
        for ca in ca_full_chain:
            tmp = {
                'ca_name' : ca.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value,
                'ca_chain' : encode_certificate(ca).replace(CERT_BEGIN, '').replace(CERT_END, '').replace('\n', ''),
            }
            data['ca_certificates'].append(tmp)

    # Remove duplicate list entries for CA certificates, as they are added by their common name
    # https://stackoverflow.com/a/9427216
    data['ca_certificates'] = [dict(t) for t in {tuple(d.items()) for d in data['ca_certificates']}]

esp_group = conf.get_config_dict(ipsec_base + ['esp-group', data['esp_group']],
                                     key_mangling=('-', '_'), get_first_key=True)
ike_proposal = conf.get_config_dict(ipsec_base + ['ike-group', data['ike_group'], 'proposal'],
                                    key_mangling=('-', '_'), get_first_key=True)

# This script works only for Apple iOS/iPadOS and Windows. Both operating systems
# have different limitations thus we load the limitations based on the operating
# system used.

vyos2client_cipher = vyos2apple_cipher if args.os == 'ios' else vyos2windows_cipher;
vyos2client_integrity = vyos2apple_integrity if args.os == 'ios' else vyos2windows_integrity;
vyos2client_dh_group = vyos2apple_dh_group if args.os == 'ios' else vyos2windows_dh_group

def transform_pfs(pfs, ike_dh_group):
    pfs_enabled = (pfs != 'disable')
    if pfs == 'enable':
        pfs_dh_group = ike_dh_group
    elif pfs.startswith('dh-group'):
        pfs_dh_group = pfs.removeprefix('dh-group')

    if args.os == 'ios':
        if pfs_enabled:
            if pfs_dh_group not in set(vyos2apple_dh_group):
                exit(f'The PFS group configured for "{args.connection}" is not supported by the client!')
            return pfs_dh_group
        else:
            return None
    else:
        if pfs_enabled:
            if pfs_dh_group not in set(vyos2windows_pfs_group):
                exit(f'The PFS group configured for "{args.connection}" is not supported by the client!')
            return vyos2windows_pfs_group[ pfs_dh_group ]
        else:
            return 'None'

# Create a dictionary containing client conform IKE settings
ike = {}
count = 1
for _, proposal in ike_proposal.items():
    if {'dh_group', 'encryption', 'hash'} <= set(proposal):
        if (proposal['encryption'] in set(vyos2client_cipher) and
            proposal['hash'] in set(vyos2client_integrity) and
            proposal['dh_group'] in set(vyos2client_dh_group)):

            # We 're-code' from the VyOS IPsec proposals to the Apple naming scheme
            proposal['encryption'] = vyos2client_cipher[ proposal['encryption'] ]
            proposal['hash'] = vyos2client_integrity[ proposal['hash'] ]
            # DH group will need to be transformed later after we calculate PFS group

            ike.update( { str(count) : proposal } )
            count += 1

# Create a dictionary containing client conform ESP settings
esp = {}
count = 1
for _, proposal in esp_group['proposal'].items():
    if {'encryption', 'hash'} <= set(proposal):
        if proposal['encryption'] in set(vyos2client_cipher) and proposal['hash'] in set(vyos2client_integrity):
            # We 're-code' from the VyOS IPsec proposals to the Apple naming scheme
            proposal['encryption'] = vyos2client_cipher[ proposal['encryption'] ]
            proposal['hash'] = vyos2client_integrity[ proposal['hash'] ]
            # Copy PFS setting from the group, if present (we will need to
            # transform this later once the IKE group is selected)
            proposal['pfs'] = esp_group.get('pfs', 'enable')

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
    elif len(ike) == 1:
        data['ike_encryption'] = ike['1']
    else:
        exit(f'None of the configured IKE proposals for "{args.connection}" are supported by the client!')

    if len(esp) > 1:
        tmp = '\n'
        for number, options in esp.items():
            tmp += f'({number}) Encryption {options["encryption"]}, Integrity {options["hash"]}\n'
        tmp += '\nSelect one of the above ESP groups: '
        data['esp_encryption'] = esp[ ask_input(tmp, valid_responses=list(esp)) ]
    elif len(esp) == 1:
        data['esp_encryption'] = esp['1']
    else:
        exit(f'None of the configured ESP  proposals for "{args.connection}" are supported by the client!')

except KeyboardInterrupt:
    exit("Interrupted")

# Transform the DH and PFS groups now that all selections are known
data['esp_encryption']['pfs'] = transform_pfs(data['esp_encryption']['pfs'], data['ike_encryption']['dh_group'])
data['ike_encryption']['dh_group'] = vyos2client_dh_group[ data['ike_encryption']['dh_group'] ]

print('\n\n==== <snip> ====')
if args.os == 'ios':
    print(render_to_string('ipsec/ios_profile.j2', data))
    print('==== </snip> ====\n')
    print('Save the XML from above to a new file named "vyos.mobileconfig" and E-Mail it to your phone.')
elif args.os == 'windows':
    print(render_to_string('ipsec/windows_profile.j2', data))
    print('==== </snip> ====\n')
