#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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

import os

from sys import exit

from vyos.base import Warning
from vyos.config import Config
from vyos.template import render
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = '/run/suricata/suricata.yaml'
rotate_file = '/etc/logrotate.d/suricata'

address_group_defaults = {
    'home-net': {'address': ['192.168.0.0/16','10.0.0.0/8','172.16.0.0/12']},
    'external-net': {'group': ['!home-net']},
    'http-servers': {'group': ['home-net']},
    'smtp-servers': {'group': ['home-net']},
    'sql-servers': {'group': ['home-net']},
    'dns-servers': {'group': ['home-net']},
    'telnet-servers': {'group': ['home-net']},
    'aim-servers': {'group': ['external-net']},
    'dc-servers': {'group': ['home-net']},
    'dnp3-server': {'group': ['home-net']},
    'modbus-client': {'group': ['home-net']},
    'modbus-server': {'group': ['home-net']},
    'enip-client': {'group': ['home-net']},
    'enip-server': {'group': ['home-net']},
}

port_group_defaults = {
    'http-ports': {'port': ['80']},
    'shellcode-ports': {'port': ['!80']},
    'oracle-ports': {'port': ['1521']},
    'ssh-ports': {'port': ['22']},
    'dnp3-ports': {'port': ['20000']},
    'modbus-ports': {'port': ['502']},
    'file-data-ports': {'port': ['110', '143'], 'group': ['http-ports']},
    'ftp-ports': {'port': ['21']},
    'geneve-ports': {'port': ['6081']},
    'vxlan-ports': {'port': ['4789']},
    'teredo-ports': {'port': ['3544']},
}

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'ids', 'suricata']
    if not conf.exists(base):
        return None

    suricata = conf.get_config_dict(base,
                                      get_first_key=True,
                                      with_recursive_defaults=True)

    # Ensure minimal defaults are present
    suricata['address-group'] = address_group_defaults | suricata.get('address-group', {})
    suricata['port-group'] = port_group_defaults | suricata.get('port-group', {})

    return suricata

# https://en.wikipedia.org/wiki/Topological_sorting#Depth-first_search
def topological_sort(source):
    sorted_nodes = []
    permanent_marks = set()
    temporary_marks = set()

    def visit(n, v):
        if n in permanent_marks:
            return
        if n in temporary_marks:
            raise ConfigError('At least one cycle exists in the referenced groups')

        temporary_marks.add(n)

        for m in v.get('group', []):
            m = m.lstrip('!')
            if m not in source:
                raise ConfigError(f'Undefined referenced group "{m}"')
            visit(m, source[m])

        temporary_marks.remove(n)
        permanent_marks.add(n)
        sorted_nodes.append((n, v))

    while len(permanent_marks) < len(source):
        n = next(n for n in source.keys() if n not in permanent_marks)
        visit(n, source[n])

    return sorted_nodes

def verify(suricata):
    if not suricata:
        return None

    if 'interface' not in suricata:
        raise ConfigError('No interfaces configured')

    try:
        topological_sort(suricata['address-group'])
    except (ConfigError,StopIteration) as e:
        raise ConfigError(f'Invalid address-group: {e}')

    try:
        topological_sort(suricata['port-group'])
    except (ConfigError,StopIteration) as e:
        raise ConfigError(f'Invalid port-group: {e}')

def generate(suricata):
    if not suricata:
        for file in [config_file, rotate_file]:
            if os.path.isfile(file):
                os.unlink(file)

        return None

    # Config-related formatters
    def to_var(s:str):
        return s.replace('-','_').upper()

    def to_val(s:str):
        return s.replace('-',':')

    def to_ref(s:str):
        if s[0] == '!':
            return '!$' + to_var(s[1:])
        return '$' + to_var(s)

    def to_config(kind:str):
        def format_group(group):
            (name, value) = group
            property = [to_val(property) for property in value.get(kind,[])]
            group = [to_ref(group) for group in value.get('group',[])]
            return (to_var(name), property + group)
        return format_group

    # Format the address group
    suricata['address-group'] = map(to_config('address'),
                                    topological_sort(suricata['address-group']))

    # Format the port group
    suricata['port-group'] = map(to_config('port'),
                                    topological_sort(suricata['port-group']))

    render(config_file, 'ids/suricata.j2', {'suricata': suricata})
    render(rotate_file, 'ids/suricata_logrotate.j2', suricata)
    return None

def apply(suricata):
    systemd_service = 'suricata.service'
    if not suricata or 'interface' not in suricata:
        # Stop suricata service if removed
        call(f'systemctl stop {systemd_service}')
    else:
        Warning('To fetch the latest rules, use "update suricata"; '
                'To periodically fetch the latest rules, '
                'use the task scheduler!')
        call(f'systemctl restart {systemd_service}')

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
