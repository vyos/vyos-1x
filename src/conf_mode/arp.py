#!/usr/bin/env python3
#
# Copyright (C) 2018-2022 VyOS maintainers and contributors
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
from vyos.configdict import node_changed
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['protocols', 'static', 'arp']
    arp = conf.get_config_dict(base, get_first_key=True)

    if 'interface' in arp:
        for interface in arp['interface']:
            tmp = node_changed(conf, base + ['interface', interface, 'address'], recursive=True)
            if tmp: arp['interface'][interface].update({'address_old' : tmp})

    return arp

def verify(arp):
    pass

def generate(arp):
    pass

def apply(arp):
    if not arp:
        return None

    if 'interface' in arp:
        for interface, interface_config in arp['interface'].items():
            # Delete old static ARP assignments first
            if 'address_old' in interface_config:
                for address in interface_config['address_old']:
                    call(f'ip neigh del {address} dev {interface}')

            # Add new static ARP entries to interface
            if 'address' not in interface_config:
                continue
            for address, address_config in interface_config['address'].items():
                mac = address_config['mac']
                call(f'ip neigh replace {address} lladdr {mac} dev {interface}')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
