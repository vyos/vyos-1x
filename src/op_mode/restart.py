#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import typing
import vyos.opmode

from vyos.configquery import ConfigTreeQuery
from vyos.utils.process import call
from vyos.utils.commit import commit_in_progress

config = ConfigTreeQuery()

service_map = {
    'dhcp': {
        'systemd_service': 'kea-dhcp4-server',
        'path': ['service', 'dhcp-server'],
    },
    'dhcpv6': {
        'systemd_service': 'kea-dhcp6-server',
        'path': ['service', 'dhcpv6-server'],
    },
    'dns_dynamic': {
        'systemd_service': 'ddclient',
        'path': ['service', 'dns', 'dynamic'],
    },
    'dns_forwarding': {
        'systemd_service': 'pdns-recursor',
        'path': ['service', 'dns', 'forwarding'],
    },
    'haproxy': {
        'systemd_service': 'haproxy',
        'path': ['load-balancing', 'haproxy'],
    },
    'igmp_proxy': {
        'systemd_service': 'igmpproxy',
        'path': ['protocols', 'igmp-proxy'],
    },
    'ipsec': {
        'systemd_service': 'strongswan',
        'path': ['vpn', 'ipsec'],
    },
    'mdns_repeater': {
        'systemd_service': 'avahi-daemon',
        'path': ['service', 'mdns', 'repeater'],
    },
    'router_advert': {
        'systemd_service': 'radvd',
        'path': ['service', 'router-advert'],
    },
    'snmp': {
        'systemd_service': 'snmpd',
    },
    'ssh': {
        'systemd_service': 'ssh',
    },
    'suricata': {
        'systemd_service': 'suricata',
    },
    'vrrp': {
        'systemd_service': 'keepalived',
        'path': ['high-availability', 'vrrp'],
    },
    'webproxy': {
        'systemd_service': 'squid',
    },
}
services = typing.Literal[
    'dhcp',
    'dhcpv6',
    'dns_dynamic',
    'dns_forwarding',
    'haproxy',
    'igmp_proxy',
    'ipsec',
    'mdns_repeater',
    'router_advert',
    'snmp',
    'ssh',
    'suricata',
    'vrrp',
    'webproxy',
]


def _verify(func):
    """Decorator checks if DHCP(v6) config exists"""
    from functools import wraps

    @wraps(func)
    def _wrapper(*args, **kwargs):
        config = ConfigTreeQuery()
        name = kwargs.get('name')
        human_name = name.replace('_', '-')

        if commit_in_progress():
            print(f'Cannot restart {human_name} service while a commit is in progress')
            sys.exit(1)

        # Get optional CLI path from service_mapping dict
        # otherwise use "service name" CLI path
        path = ['service', name]
        if 'path' in service_map[name]:
            path = service_map[name]['path']

        # Check if config does not exist
        if not config.exists(path):
            raise vyos.opmode.UnconfiguredSubsystem(
                f'Service {human_name} is not configured!'
            )
        if config.exists(path + ['disable']):
            raise vyos.opmode.UnconfiguredSubsystem(
                f'Service {human_name} is disabled!'
            )
        return func(*args, **kwargs)

    return _wrapper


@_verify
def restart_service(raw: bool, name: services, vrf: typing.Optional[str]):
    systemd_service = service_map[name]['systemd_service']
    if vrf:
        call(f'systemctl restart "{systemd_service}@{vrf}.service"')
    else:
        call(f'systemctl restart "{systemd_service}.service"')


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
