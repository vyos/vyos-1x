#!/usr/bin/env python3
#
# Copyright (C) 2022-2024 VyOS maintainers and contributors
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

import argparse

from jinja2 import Template
from textwrap import fill

from vyos.configquery import ConfigTreeQuery
from vyos.ifconfig import Section

client_config = """

client
nobind
remote {{ remote_host }} {{ port }}
remote-cert-tls server
proto {{ 'tcp-client' if protocol == 'tcp-active' else 'udp' }}
dev {{ device }}
dev-type {{ device }}
persist-key
persist-tun
verb 3

# Encryption options
{% if encryption is defined and encryption is not none %}
{%   if encryption.cipher is defined and encryption.cipher is not none %}
cipher {{ encryption.cipher }}
{%     if encryption.cipher == 'bf128' %}
keysize 128
{%     elif encryption.cipher == 'bf256' %}
keysize 256
{%     endif %}
{%   endif %}
{%   if encryption.ncp_ciphers is defined and encryption.ncp_ciphers is not none %}
data-ciphers {{ encryption.ncp_ciphers }}
{%   endif %}
{% endif %}

{% if hash is defined and hash is not none %}
auth {{ hash }}
{% endif %}
keysize 256
comp-lzo {{ '' if use_lzo_compression is defined else 'no' }}

<ca>
-----BEGIN CERTIFICATE-----
{{ ca }}
-----END CERTIFICATE-----

</ca>

<cert>
-----BEGIN CERTIFICATE-----
{{ cert }}
-----END CERTIFICATE-----

</cert>

<key>
-----BEGIN PRIVATE KEY-----
{{ key }}
-----END PRIVATE KEY-----

</key>

"""

config = ConfigTreeQuery()
base = ['interfaces', 'openvpn']

if not config.exists(base):
    print('OpenVPN not configured')
    exit(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--interface", type=str, help='OpenVPN interface the client is connecting to', required=True)
    parser.add_argument("-a", "--ca", type=str, help='OpenVPN CA cerificate', required=True)
    parser.add_argument("-c", "--cert", type=str, help='OpenVPN client cerificate', required=True)
    parser.add_argument("-k", "--key", type=str, help='OpenVPN client cerificate key', action="store")
    args = parser.parse_args()

    interface = args.interface
    ca = args.ca
    cert = args.cert
    key = args.key
    if not key:
        key = args.cert

    if interface not in Section.interfaces('openvpn'):
        exit(f'OpenVPN interface "{interface}" does not exist!')

    if not config.exists(['pki', 'ca', ca, 'certificate']):
        exit(f'OpenVPN CA certificate "{ca}" does not exist!')

    if not config.exists(['pki', 'certificate', cert, 'certificate']):
        exit(f'OpenVPN certificate "{cert}" does not exist!')

    if not config.exists(['pki', 'certificate', cert, 'private', 'key']):
        exit(f'OpenVPN certificate key "{key}" does not exist!')

    ca = config.value(['pki', 'ca', ca, 'certificate'])
    ca = fill(ca, width=64)
    cert = config.value(['pki', 'certificate', cert, 'certificate'])
    cert = fill(cert, width=64)
    key = config.value(['pki', 'certificate', key, 'private', 'key'])
    key = fill(key, width=64)
    remote_host = config.value(base + [interface, 'local-host'])

    ovpn_conf = config.get_config_dict(base + [interface], key_mangling=('-', '_'), get_first_key=True)

    port = '1194' if 'local_port' not in ovpn_conf else ovpn_conf['local_port']
    proto = 'udp' if 'protocol' not in ovpn_conf else ovpn_conf['protocol']
    device = 'tun' if 'device_type' not in ovpn_conf else ovpn_conf['device_type']

    config = {
        'interface'   : interface,
        'ca'          : ca,
        'cert'        : cert,
        'key'         : key,
        'device'      : device,
        'port'        : port,
        'proto'       : proto,
        'remote_host' : remote_host,
        'address'     : [],
    }

# Clear out terminal first
print('\x1b[2J\x1b[H')
client = Template(client_config, trim_blocks=True).render(config)
print(client)
