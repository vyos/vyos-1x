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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse

from jinja2 import Template
from sys import exit
from socket import getfqdn

from vyos.config import Config
from vyos.template import render_to_string
from cryptography.x509.oid import NameOID
from vyos.pki import load_certificate

parser = argparse.ArgumentParser()
parser.add_argument("--connection", action="store", help="IPsec IKEv2 remote-access connection name from CLI", required=True)
parser.add_argument("--remote", action="store", help="VPN connection remote-address where the client will connect to", required=True)
parser.add_argument("--profile", action="store", help="IKEv2 profile name used in the profile list on the device")
parser.add_argument("--name", action="store", help="VPN connection name as seen in the VPN application later")
args = parser.parse_args()

ipsec_base = ['vpn', 'ipsec']
config_base = ipsec_base +  ['remote-access', 'connection']
pki_base = ['pki']
conf = Config()
if not conf.exists(config_base):
    exit('IPSec remote-access is not configured!')

profile_name = 'VyOS IKEv2 Profile'
if args.profile:
    profile_name = args.profile

vpn_name = 'VyOS IKEv2 Profile'
if args.name:
    vpn_name = args.name

conn_base = config_base + [args.connection]
if not conf.exists(conn_base):
     exit(f'IPSec remote-access connection "{args.connection}" does not exist!')

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
ca_name = data['authentication']['x509']['ca_certificate']
cert_name = data['authentication']['x509']['certificate']

ca_cert = load_certificate(pki['ca'][ca_name]['certificate'])
cert = load_certificate(pki['certificate'][cert_name]['certificate'])

data['ca_cn'] = ca_cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
data['cert_cn'] = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
data['ca_cert'] = conf.return_value(pki_base + ['ca', ca_name, 'certificate'])

data['esp_proposal'] = conf.get_config_dict(ipsec_base + ['esp-group', data['esp_group'], 'proposal'], key_mangling=('-', '_'), get_first_key=True)
data['ike_proposal'] = conf.get_config_dict(ipsec_base + ['ike-group', data['ike_group'], 'proposal'], key_mangling=('-', '_'), get_first_key=True)

print(render_to_string('ipsec/ios_profile.tmpl', data))
