#!/usr/bin/env python3
#
# Copyright (C) 2021-2022 VyOS maintainers and contributors
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
import uuid
import netifaces
from ipaddress import IPv4Network
from ipaddress import IPv6Network

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.util import call
from vyos.template import render
from vyos.template import is_ipv4
from vyos.template import is_ipv6
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = r'/run/upnp/miniupnp.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['service', 'upnp']
    upnpd = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    if not upnpd:
        return None

    if 'rule' in upnpd:
        default_member_values = defaults(base + ['rule'])
        for rule,rule_config in upnpd['rule'].items():
            upnpd['rule'][rule] = dict_merge(default_member_values, upnpd['rule'][rule])

    uuidgen = uuid.uuid1()
    upnpd.update({'uuid': uuidgen})

    return upnpd

def get_all_interface_addr(prefix, filter_dev, filter_family):
    list_addr = []
    interfaces = netifaces.interfaces()

    for interface in interfaces:
        if filter_dev and interface in filter_dev:
            continue
        addrs = netifaces.ifaddresses(interface)
        if netifaces.AF_INET in addrs.keys():
            if netifaces.AF_INET in filter_family:
                for addr in addrs[netifaces.AF_INET]:
                    if prefix:
                        # we need to manually assemble a list of IPv4 address/prefix
                        prefix = '/' + \
                            str(IPv4Network('0.0.0.0/' + addr['netmask']).prefixlen)
                        list_addr.append(addr['addr'] + prefix)
                    else:
                        list_addr.append(addr['addr'])
        if netifaces.AF_INET6 in addrs.keys():
            if netifaces.AF_INET6 in filter_family:
                for addr in addrs[netifaces.AF_INET6]:
                    if prefix:
                        # we need to manually assemble a list of IPv4 address/prefix
                        bits = bin(int(addr['netmask'].replace(':', '').split('/')[0], 16)).count('1')
                        prefix = '/' + str(bits)
                        list_addr.append(addr['addr'] + prefix)
                    else:
                        list_addr.append(addr['addr'])

    return list_addr

def verify(upnpd):
    if not upnpd:
        return None

    if 'wan_interface' not in upnpd:
        raise ConfigError('To enable UPNP, you must have the "wan-interface" option!')

    if 'rule' in upnpd:
        for rule, rule_config in upnpd['rule'].items():
            for option in ['external_port_range', 'internal_port_range', 'ip', 'action']:
                if option not in rule_config:
                    tmp = option.replace('_', '-')
                    raise ConfigError(f'Every UPNP rule requires "{tmp}" to be set!')

    if 'stun' in upnpd:
        for option in ['host', 'port']:
            if option not in upnpd['stun']:
                raise ConfigError(f'A UPNP stun support must have an "{option}" option!')

    # Check the validity of the IP address
    listen_dev = []
    system_addrs_cidr = get_all_interface_addr(True, [], [netifaces.AF_INET, netifaces.AF_INET6])
    system_addrs = get_all_interface_addr(False, [], [netifaces.AF_INET, netifaces.AF_INET6])
    if 'listen' not in upnpd:
        raise ConfigError(f'Listen address or interface is required!')
    for listen_if_or_addr in upnpd['listen']:
        if listen_if_or_addr not in netifaces.interfaces():
            listen_dev.append(listen_if_or_addr)
        if (listen_if_or_addr not in system_addrs) and (listen_if_or_addr not in system_addrs_cidr) and \
                (listen_if_or_addr not in netifaces.interfaces()):
            if is_ipv4(listen_if_or_addr) and IPv4Network(listen_if_or_addr).is_multicast:
                raise ConfigError(f'The address "{listen_if_or_addr}" is an address that is not allowed'
                                  f'to listen on. It is not an interface address nor a multicast address!')
            if is_ipv6(listen_if_or_addr) and IPv6Network(listen_if_or_addr).is_multicast:
                raise ConfigError(f'The address "{listen_if_or_addr}" is an address that is not allowed'
                                  f'to listen on. It is not an interface address nor a multicast address!')

    system_listening_dev_addrs_cidr = get_all_interface_addr(True, listen_dev, [netifaces.AF_INET6])
    system_listening_dev_addrs = get_all_interface_addr(False, listen_dev, [netifaces.AF_INET6])
    for listen_if_or_addr in upnpd['listen']:
        if listen_if_or_addr not in netifaces.interfaces() and \
                (listen_if_or_addr not in system_listening_dev_addrs_cidr) and \
                (listen_if_or_addr not in system_listening_dev_addrs) and \
                is_ipv6(listen_if_or_addr) and \
                (not IPv6Network(listen_if_or_addr).is_multicast):
            raise ConfigError(f'{listen_if_or_addr} must listen on the interface of the network card')

def generate(upnpd):
    if not upnpd:
        return None

    if os.path.isfile(config_file):
        os.unlink(config_file)

    render(config_file, 'firewall/upnpd.conf.j2', upnpd)

def apply(upnpd):
    systemd_service_name = 'miniupnpd.service'
    if not upnpd:
        # Stop the UPNP service
        call(f'systemctl stop {systemd_service_name}')
    else:
        # Start the UPNP service
        call(f'systemctl restart {systemd_service_name}')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
