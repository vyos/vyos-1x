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

from json import loads
from sys import exit

from vyos.base import Warning
from vyos.config import Config
from vyos.ifconfig.vrrp import VRRP
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.dict import dict_search
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = r'/run/dhcp-relay/dhcrelay.conf'
vrrp_running_file = '/run/dhcp4_vrrp_active'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'dhcp-relay']
    if not conf.exists(base):
        return None

    relay = conf.get_config_dict(base, key_mangling=('-', '_'),
                                 get_first_key=True,
                                 with_recursive_defaults=True)

    if relay:
        relay['vrrp_exists'] = conf.exists('high-availability vrrp')

    return relay

def verify(relay):
    # bail out early - looks like removal from running config
    if not relay or 'disable' in relay:
        return None

    if 'lo' in (dict_search('interface', relay) or []):
        raise ConfigError('DHCP relay does not support the loopback interface.')

    if 'server' not in relay :
        raise ConfigError('No DHCP relay server(s) configured.\n' \
                          'At least one DHCP relay server required.')

    if 'interface' in relay:
        Warning('DHCP relay interface is DEPRECATED - please use upstream-interface and listen-interface instead!')
        if 'upstream_interface' in relay or 'listen_interface' in relay:
            raise ConfigError('<interface> configuration is not compatible with upstream/listen interface')
        else:
            Warning('<interface> is going to be deprecated.\n'  \
                    'Please use <listen-interface> and <upstream-interface>')

    if 'upstream_interface' in relay and 'listen_interface' not in relay:
        raise ConfigError('No listen-interface configured')
    if 'listen_interface' in relay and 'upstream_interface' not in relay:
        raise ConfigError('No upstream-interface configured')

    return None

# Get VRRP states from interfaces, returns only interfaces where state is MASTER
def filter_interfaces_vrrp(interfaces: list[str]) -> None:
    """Remove any interfaces from the given list that are no in VRRP MASTER state."""
    json_data = loads(VRRP.collect('json'))
    for group in json_data:
        if 'data' in group:
            if 'ifp_ifname' in group['data']:
                iface = group['data']['ifp_ifname']
                state = group['data']['state'] # 2 = Master
                if iface in interfaces and state != 2:
                    interfaces.remove(iface)

def generate(relay):
    # bail out early - looks like removal from running config
    if not relay or 'disable' in relay:
        return None

    if relay['vrrp_exists'] and 'vrrp_disable' in relay:
        filter_interfaces_vrrp(relay['listen_interface'])

        if len(relay['listen_interface']) == 0:
            return None

    render(config_file, 'dhcp-relay/dhcrelay.conf.j2', relay)
    return None

def apply(relay):
    # bail out early - looks like removal from running config
    service_name = 'isc-dhcp-relay.service'

    if (not relay or 'vrrp_disable' not in relay) and os.path.exists(vrrp_running_file):
        os.unlink(vrrp_running_file)
    elif relay['vrrp_exists'] and 'vrrp_disable' in relay and not os.path.exists(vrrp_running_file):
        os.mknod(vrrp_running_file) # vrrp script looks for this file to update DHCP relay
 
    if not relay or 'disable' in relay:
        call(f'systemctl stop {service_name}')
        if os.path.exists(config_file):
            os.unlink(config_file)
        return None
    elif relay['vrrp_exists'] and 'vrrp_disable' in relay and len(relay['listen_interface']) == 0:
        call(f'systemctl stop {service_name}')
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
