#!/usr/bin/env python3
#
# Copyright (C) 2018-2023 VyOS maintainers and contributors
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
import time

from sys import exit
from ipaddress import ip_interface
from ipaddress import IPv4Interface
from ipaddress import IPv6Interface

from vyos.base import Warning
from vyos.config import Config
from vyos.configdict import leaf_node_changed
from vyos.ifconfig.vrrp import VRRP
from vyos.template import render
from vyos.template import is_ipv4
from vyos.template import is_ipv6
from vyos.utils.network import is_ipv6_tentative
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()


systemd_override = r'/run/systemd/system/keepalived.service.d/10-override.conf'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['high-availability']
    if not conf.exists(base):
        return None

    ha = conf.get_config_dict(base, key_mangling=('-', '_'),
                              no_tag_node_value_mangle=True,
                              get_first_key=True, with_defaults=True)

    ## Get the sync group used for conntrack-sync
    conntrack_path = ['service', 'conntrack-sync', 'failover-mechanism', 'vrrp', 'sync-group']
    if conf.exists(conntrack_path):
        ha['conntrack_sync_group'] = conf.return_value(conntrack_path)

    if leaf_node_changed(conf, base + ['vrrp', 'snmp']):
        ha.update({'restart_required': {}})

    return ha

def verify(ha):
    if not ha or 'disable' in ha:
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

            if 'health_check' in group_config:
                _validate_health_check(group, group_config)

            # Keepalived doesn't allow mixing IPv4 and IPv6 in one group, so we mirror that restriction
            # We also need to make sure VRID is not used twice on the same interface with the
            # same address family.

            interface = group_config['interface']
            vrid = group_config['vrid']

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
                tmp = {'interface': interface, 'vrid': vrid, 'ipver': 'IPv4'}
                if tmp in used_vrid_if:
                    raise ConfigError(f'VRID "{vrid}" can only be used once on interface "{interface} with address family IPv4"!')
                used_vrid_if.append(tmp)

                if 'hello_source_address' in group_config:
                    if is_ipv6(group_config['hello_source_address']):
                        raise ConfigError(f'VRRP group "{group}" uses IPv4 but hello-source-address is IPv6!')

                if 'peer_address' in group_config:
                    for peer_address in group_config['peer_address']:
                        if is_ipv6(peer_address):
                            raise ConfigError(f'VRRP group "{group}" uses IPv4 but peer-address is IPv6!')

            if vaddrs6:
                tmp = {'interface': interface, 'vrid': vrid, 'ipver': 'IPv6'}
                if tmp in used_vrid_if:
                    raise ConfigError(f'VRID "{vrid}" can only be used once on interface "{interface} with address family IPv6"!')
                used_vrid_if.append(tmp)

                if 'hello_source_address' in group_config:
                    if is_ipv4(group_config['hello_source_address']):
                        raise ConfigError(f'VRRP group "{group}" uses IPv6 but hello-source-address is IPv4!')

                if 'peer_address' in group_config:
                    for peer_address in group_config['peer_address']:
                        if is_ipv4(peer_address):
                            raise ConfigError(f'VRRP group "{group}" uses IPv6 but peer-address is IPv4!')
    # Check sync groups
    if 'vrrp' in ha and 'sync_group' in ha['vrrp']:
        for sync_group, sync_config in ha['vrrp']['sync_group'].items():
            if 'health_check' in sync_config:
                _validate_health_check(sync_group, sync_config)

            if 'member' in sync_config:
                for member in sync_config['member']:
                    if member not in ha['vrrp']['group']:
                        raise ConfigError(f'VRRP sync-group "{sync_group}" refers to VRRP group "{member}", '\
                                          'but it does not exist!')
                    else:
                        ha['vrrp']['group'][member]['_is_sync_group_member'] = True
                        if ha['vrrp']['group'][member].get('health_check') is not None:
                            raise ConfigError(
                                f'Health check configuration for VRRP group "{member}" will remain unused '
                                f'while it has member of sync group "{sync_group}" '
                                f'Only sync group health check will be used'
                            )

    # Virtual-server
    if 'virtual_server' in ha:
        for vs, vs_config in ha['virtual_server'].items():

            if 'address' not in vs_config and 'fwmark' not in vs_config:
                raise ConfigError('Either address or fwmark is required '
                                  f'but not set for virtual-server "{vs}"')

            if 'port' not in vs_config and 'fwmark' not in vs_config:
                raise ConfigError(f'Port or fwmark is required but not set for virtual-server "{vs}"')
            if 'port' in vs_config and 'fwmark' in vs_config:
                raise ConfigError(f'Cannot set both port and fwmark for virtual-server "{vs}"')
            if 'real_server' not in vs_config:
                raise ConfigError(f'Real-server ip is required but not set for virtual-server "{vs}"')
        # Real-server
        for rs, rs_config in vs_config['real_server'].items():
            if 'port' not in rs_config:
                raise ConfigError(f'Port is required but not set for virtual-server "{vs}" real-server "{rs}"')


def _validate_health_check(group, group_config):
    health_check_types = ["script", "ping"]
    from vyos.utils.dict import check_mutually_exclusive_options
    try:
        check_mutually_exclusive_options(group_config["health_check"],
                                         health_check_types, required=True)
    except ValueError:
        Warning(
            f'Health check configuration for VRRP group "{group}" will remain unused ' \
            f'until it has one of the following options: {health_check_types}')
        # XXX: health check has default options so we need to remove it
        # to avoid generating useless config statements in keepalived.conf
        del group_config["health_check"]


def generate(ha):
    if not ha or 'disable' in ha:
        if os.path.isfile(systemd_override):
            os.unlink(systemd_override)
        return None

    render(VRRP.location['config'], 'high-availability/keepalived.conf.j2', ha)
    render(systemd_override, 'high-availability/10-override.conf.j2', ha)
    return None

def apply(ha):
    service_name = 'keepalived.service'
    call('systemctl daemon-reload')
    if not ha or 'disable' in ha:
        call(f'systemctl stop {service_name}')
        return None

    # Check if IPv6 address is tentative T5533
    for group, group_config in ha.get('vrrp', {}).get('group', {}).items():
        if 'hello_source_address' in group_config:
            if is_ipv6(group_config['hello_source_address']):
                ipv6_address = group_config['hello_source_address']
                interface = group_config['interface']
                checks = 20
                interval = 0.1
                for _ in range(checks):
                    if is_ipv6_tentative(interface, ipv6_address):
                        time.sleep(interval)

    systemd_action = 'reload-or-restart'
    if 'restart_required' in ha:
        systemd_action = 'restart'

    call(f'systemctl {systemd_action} {service_name}')
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
