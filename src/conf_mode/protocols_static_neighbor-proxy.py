#!/usr/bin/env python3
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
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

from sys import exit

from vyos.config import Config
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['protocols', 'static', 'neighbor-proxy']
    config = conf.get_config_dict(base, get_first_key=True)

    return config

def verify(config):
    if 'arp' in config:
        for neighbor, neighbor_conf in config['arp'].items():
            if 'interface' not in neighbor_conf:
                raise ConfigError(
                    f"ARP neighbor-proxy for '{neighbor}' requires an interface to be set!"
                )

    if 'nd' in config:
        for neighbor, neighbor_conf in config['nd'].items():
            if 'interface' not in neighbor_conf:
                raise ConfigError(
                    f"ARP neighbor-proxy for '{neighbor}' requires an interface to be set!"
                )

def generate(config):
    pass

def apply(config):
    if not config:
        # Cleanup proxy
        call('ip neighbor flush proxy')
        call('ip -6 neighbor flush proxy')
        return None

    # Add proxy ARP
    if 'arp' in config:
        # Cleanup entries before config
        call('ip neighbor flush proxy')
        for neighbor, neighbor_conf in config['arp'].items():
            for interface in neighbor_conf.get('interface'):
                call(f'ip neighbor add proxy {neighbor} dev {interface}')

    # Add proxy NDP
    if 'nd' in config:
        # Cleanup entries before config
        call('ip -6 neighbor flush proxy')
        for neighbor, neighbor_conf in config['nd'].items():
            for interface in neighbor_conf['interface']:
                call(f'ip -6 neighbor add proxy {neighbor} dev {interface}')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
