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

from vyos.config import Config
from vyos.ifconfig import Section

client_config = """

client
nobind
remote {{ local_host if local_host else 'x.x.x.x' }} {{ port }}
remote-cert-tls server
proto {{ 'tcp-client' if protocol == 'tcp-passive' else 'udp' }}
dev {{ device_type }}
dev-type {{ device_type }}
persist-key
persist-tun
verb 3

# Encryption options
{# Define the encryption map #}
{% set encryption_map = {
    'des': 'DES-CBC',
    '3des': 'DES-EDE3-CBC',
    'bf128': 'BF-CBC',
    'bf256': 'BF-CBC',
    'aes128gcm': 'AES-128-GCM',
    'aes128': 'AES-128-CBC',
    'aes192gcm': 'AES-192-GCM',
    'aes192': 'AES-192-CBC',
    'aes256gcm': 'AES-256-GCM',
    'aes256': 'AES-256-CBC'
} %}

{% if encryption is defined and encryption is not none %}
{%     if encryption.data_ciphers is defined and encryption.data_ciphers is not none %}
cipher {% for algo in encryption.data_ciphers %}
{{ encryption_map[algo] if algo in encryption_map.keys() else algo }}{% if not loop.last %}:{% endif %}
{%      endfor %}

data-ciphers {% for algo in encryption.data_ciphers %}
{{ encryption_map[algo] if algo in encryption_map.keys() else algo }}{% if not loop.last %}:{% endif %}
{%      endfor %}
{%     endif %}
{% endif %}

{% if hash is defined and hash is not none %}
auth {{ hash }}
{% endif %}
{{ 'comp-lzo' if use_lzo_compression is defined else '' }}

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

config = Config()
base = ['interfaces', 'openvpn']

if not config.exists(base):
    print('OpenVPN not configured')
    exit(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--interface",
        type=str,
        help='OpenVPN interface the client is connecting to',
        required=True,
    )
    parser.add_argument(
        "-a", "--ca", type=str, help='OpenVPN CA cerificate', required=True
    )
    parser.add_argument(
        "-c", "--cert", type=str, help='OpenVPN client cerificate', required=True
    )
    parser.add_argument(
        "-k", "--key", type=str, help='OpenVPN client cerificate key', action="store"
    )
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

    config = config.get_config_dict(
        base + [interface],
        key_mangling=('-', '_'),
        get_first_key=True,
        with_recursive_defaults=True,
        with_pki=True,
    )

    ca = config['pki']['ca'][ca]['certificate']
    ca = fill(ca, width=64)
    cert = config['pki']['certificate'][cert]['certificate']
    cert = fill(cert, width=64)
    key = config['pki']['certificate'][key]['private']['key']
    key = fill(key, width=64)

    config['ca'] = ca
    config['cert'] = cert
    config['key'] = key
    config['port'] = '1194' if 'local_port' not in config else config['local_port']

    client = Template(client_config, trim_blocks=True).render(config)
    print(client)
