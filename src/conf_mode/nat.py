#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

from copy import deepcopy
from sys import exit
from netifaces import interfaces

from vyos.config import Config
from vyos.util import call
from vyos.template import render
from vyos import ConfigError

default_config_data = {
    'source': [],
    'destination': []
}

iptables_nat_config = '/tmp/iptables_nat_config'

def parse_source_destination(conf, source_dest):
    """ Common wrapper to read in both NAT source and destination CLI """
    tmp = []
    base_level = ['nat', source_dest]
    conf.set_level(base_level)
    for number in conf.list_nodes(['rule']):
        rule = {
            'description': '',
            'dest_address': '',
            'dest_port': '',
            'disable': False,
            'exclude': False,
            'interface_in': '',
            'interface_out': '',
            'log': False,
            'protocol': '',
            'number': number,
            'source_address': '',
            'source_port': '',
            'translation_address': '',
            'translation_port': ''
        }
        conf.set_level(base_level + ['rule', number])

        if conf.exists(['description']):
            rule['description'] = conf.return_value(['description'])

        if conf.exists(['destination', 'address']):
            rule['dest_address'] = conf.return_value(['destination', 'address'])

        if conf.exists(['destination', 'port']):
            rule['dest_port'] = conf.return_value(['destination', 'port'])

        if conf.exists(['disable']):
            rule['disable'] = True

        if conf.exists(['exclude']):
            rule['exclude'] = True

        if conf.exists(['inbound-interface']):
            rule['interface_in'] = conf.return_value(['inbound-interface'])

        if conf.exists(['outbound-interface']):
            rule['interface_out'] = conf.return_value(['outbound-interface'])

        if conf.exists(['log']):
            rule['log'] = True

        if conf.exists(['protocol']):
            rule['protocol'] = conf.return_value(['protocol'])

        if conf.exists(['source', 'address']):
            rule['source_address'] = conf.return_value(['source', 'address'])

        if conf.exists(['source', 'port']):
            rule['source_port'] = conf.return_value(['source', 'port'])

        if conf.exists(['translation', 'address']):
            rule['translation_address'] = conf.return_value(['translation', 'address'])

        if conf.exists(['translation', 'port']):
            rule['translation_port'] = conf.return_value(['translation', 'port'])

        tmp.append(rule)

    return tmp

def get_config():
    nat = deepcopy(default_config_data)
    conf = Config()
    if not conf.exists(['nat']):
        return None
    else:
        conf.set_level(['nat'])

    # use a common wrapper function to read in the source / destination
    # tree from the config - thus we do not need to replicate almost the
    # same code :-)
    for tgt in ['source', 'destination']:
        nat[tgt] = parse_source_destination(conf, tgt)

    return nat

def verify(nat):
    if not nat:
        return None

    for rule in nat['source']:
        interface = rule['interface_out']
        if interface and interface not in interfaces():
            print(f'NAT configuration warning: interface {interface} does not exist on this system')

    return None

def generate(nat):
    if not nat:
        return None

    render(iptables_nat_config, 'nat/iptables-restore.tmpl', nat, trim_blocks=True)
    return None

def apply(nat):
    if not nat:
        return None

    call(f'iptables-restore --test < {iptables_nat_config}')

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
