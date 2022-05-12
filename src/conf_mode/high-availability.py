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

import os

from sys import exit
from ipaddress import ip_interface
from ipaddress import IPv4Interface
from ipaddress import IPv6Interface

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.ifconfig.vrrp import VRRP
from vyos.template import render
from vyos.template import is_ipv4
from vyos.template import is_ipv6
from vyos.util import call
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['high-availability']
    base_vrrp = ['high-availability', 'vrrp']
    if not conf.exists(base):
        return None

    ha = conf.get_config_dict(base, key_mangling=('-', '_'),
                                get_first_key=True, no_tag_node_value_mangle=True)
    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    if 'vrrp' in ha:
        if 'group' in ha['vrrp']:
            default_values_vrrp = defaults(base_vrrp + ['group'])
            for group in ha['vrrp']['group']:
                ha['vrrp']['group'][group] = dict_merge(default_values_vrrp, ha['vrrp']['group'][group])

    # Merge per virtual-server default values
    if 'virtual_server' in ha:
        default_values = defaults(base + ['virtual-server'])
        for vs in ha['virtual_server']:
            ha['virtual_server'][vs] = dict_merge(default_values, ha['virtual_server'][vs])

    ## Get the sync group used for conntrack-sync
    conntrack_path = ['service', 'conntrack-sync', 'failover-mechanism', 'vrrp', 'sync-group']
    if conf.exists(conntrack_path):
        ha['conntrack_sync_group'] = conf.return_value(conntrack_path)

    return ha

def verify(ha):
    if not ha:
        return None

    used_vrid_if = []
    if 'vrrp' in ha and 'group' in ha['vrrp']:
        for group, group_config in ha['vrrp']['group'].items():
            # Check required fields
            if 'vrid' not in group_config:
                raise ConfigError(f'VRID is required but not set in VRRP group "{group}"')

            if 'interface' not in group_config:
                raise ConfigError(f'Interface is required but not set in VRRP group "{group}"')

            if 'address' not in group_config:
                raise ConfigError(f'Virtual IP address is required but not set in VRRP group "{group}"')

            if 'authentication' in group_config:
                if not {'password', 'type'} <= set(group_config['authentication']):
                    raise ConfigError(f'Authentication requires both type and passwortd to be set in VRRP group "{group}"')

            # We can not use a VRID once per interface
            interface = group_config['interface']
            vrid = group_config['vrid']
            tmp = {'interface': interface, 'vrid': vrid}
            if tmp in used_vrid_if:
                raise ConfigError(f'VRID "{vrid}" can only be used once on interface "{interface}"!')
            used_vrid_if.append(tmp)

            # Keepalived doesn't allow mixing IPv4 and IPv6 in one group, so we mirror that restriction

            # XXX: filter on map object is destructive, so we force it to list.
            # Additionally, filter objects always evaluate to True, empty or not,
            # so we force them to lists as well.
            vaddrs = list(map(lambda i: ip_interface(i), group_config['address']))
            vaddrs4 = list(filter(lambda x: isinstance(x, IPv4Interface), vaddrs))
            vaddrs6 = list(filter(lambda x: isinstance(x, IPv6Interface), vaddrs))

            if vaddrs4 and vaddrs6:
                raise ConfigError(f'VRRP group "{group}" mixes IPv4 and IPv6 virtual addresses, this is not allowed.\n' \
                                  'Create individual groups for IPv4 and IPv6!')
            if vaddrs4:
                if 'hello_source_address' in group_config:
                    if is_ipv6(group_config['hello_source_address']):
                        raise ConfigError(f'VRRP group "{group}" uses IPv4 but hello-source-address is IPv6!')

                if 'peer_address' in group_config:
                    if is_ipv6(group_config['peer_address']):
                        raise ConfigError(f'VRRP group "{group}" uses IPv4 but peer-address is IPv6!')

            if vaddrs6:
                if 'hello_source_address' in group_config:
                    if is_ipv4(group_config['hello_source_address']):
                        raise ConfigError(f'VRRP group "{group}" uses IPv6 but hello-source-address is IPv4!')

                if 'peer_address' in group_config:
                    if is_ipv4(group_config['peer_address']):
                        raise ConfigError(f'VRRP group "{group}" uses IPv6 but peer-address is IPv4!')
    # Check sync groups
    if 'vrrp' in ha and 'sync_group' in ha['vrrp']:
        for sync_group, sync_config in ha['vrrp']['sync_group'].items():
            if 'member' in sync_config:
                for member in sync_config['member']:
                    if member not in ha['vrrp']['group']:
                        raise ConfigError(f'VRRP sync-group "{sync_group}" refers to VRRP group "{member}", '\
                                          'but it does not exist!')

    # Virtual-server
    if 'virtual_server' in ha:
        for vs, vs_config in ha['virtual_server'].items():
            if 'port' not in vs_config:
                raise ConfigError(f'Port is required but not set for virtual-server "{vs}"')
            if 'real_server' not in vs_config:
                raise ConfigError(f'Real-server ip is required but not set for virtual-server "{vs}"')
        # Real-server
        for rs, rs_config in vs_config['real_server'].items():
            if 'port' not in rs_config:
                raise ConfigError(f'Port is required but not set for virtual-server "{vs}" real-server "{rs}"')


def generate(ha):
    if not ha:
        return None

    render(VRRP.location['config'], 'high-availability/keepalived.conf.j2', ha)
    return None

def apply(ha):
    service_name = 'keepalived.service'
    if not ha:
        call(f'systemctl stop {service_name}')
        return None

    call(f'systemctl reload-or-restart {service_name}')
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
