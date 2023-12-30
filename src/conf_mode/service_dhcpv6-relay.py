#!/usr/bin/env python3
#
# Copyright (C) 2018-2020 VyOS maintainers and contributors
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

from vyos.config import Config
from vyos.ifconfig import Interface
from vyos.template import render
from vyos.template import is_ipv6
from vyos.utils.process import call
from vyos.utils.network import is_ipv6_link_local
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = '/run/dhcp-relay/dhcrelay6.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'dhcpv6-relay']
    if not conf.exists(base):
        return None

    relay = conf.get_config_dict(base, key_mangling=('-', '_'),
                                 get_first_key=True,
                                 with_recursive_defaults=True)

    return relay

def verify(relay):
    # bail out early - looks like removal from running config
    if not relay or 'disable' in relay:
        return None

    if 'upstream_interface' not in relay:
        raise ConfigError('At least one upstream interface required!')
    for interface, config in relay['upstream_interface'].items():
        if 'address' not in config:
            raise ConfigError('DHCPv6 server required for upstream ' \
                              f'interface {interface}!')

    if 'listen_interface' not in relay:
        raise ConfigError('At least one listen interface required!')

    # DHCPv6 relay requires at least one global unicat address assigned to the
    # interface
    for interface in relay['listen_interface']:
        has_global = False
        for addr in Interface(interface).get_addr():
            if is_ipv6(addr) and not is_ipv6_link_local(addr):
                has_global = True
        if not has_global:
            raise ConfigError(f'Interface {interface} does not have global '\
                              'IPv6 address assigned!')

    return None

def generate(relay):
    # bail out early - looks like removal from running config
    if not relay or 'disable' in relay:
        return None

    render(config_file, 'dhcp-relay/dhcrelay6.conf.j2', relay)
    return None

def apply(relay):
    # bail out early - looks like removal from running config
    service_name = 'isc-dhcp-relay6.service'
    if not relay or 'disable' in relay:
        # DHCPv6 relay support is removed in the commit
        call(f'systemctl stop {service_name}')
        if os.path.exists(config_file):
            os.unlink(config_file)
        return None

    call(f'systemctl restart {service_name}')

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
