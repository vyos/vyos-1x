#!/usr/bin/env python3
#
# Copyright (C) 2017-2022 VyOS maintainers and contributors
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
from netifaces import ifaddresses, interfaces, AF_INET

from vyos.config import Config
from vyos.ifconfig.vrrp import VRRP
from vyos.template import render
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = '/run/avahi-daemon/avahi-daemon.conf'
vrrp_running_file = '/run/mdns_vrrp_active'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'mdns', 'repeater']
    mdns = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    if mdns:
        mdns['vrrp_exists'] = conf.exists('high-availability vrrp')
    return mdns

def verify(mdns):
    if not mdns:
        return None

    if 'disable' in mdns:
        return None

    # We need at least two interfaces to repeat mDNS advertisments
    if 'interface' not in mdns or len(mdns['interface']) < 2:
        raise ConfigError('mDNS repeater requires at least 2 configured interfaces!')

    # For mdns-repeater to work it is essential that the interfaces has
    # an IPv4 address assigned
    for interface in mdns['interface']:
        if interface not in interfaces():
            raise ConfigError(f'Interface "{interface}" does not exist!')

        if AF_INET not in ifaddresses(interface):
            raise ConfigError('mDNS repeater requires an IPv4 address to be '
                                  f'configured on interface "{interface}"')

    return None

# Get VRRP states from interfaces, returns only interfaces where state is MASTER
def get_vrrp_master(interfaces):
    json_data = loads(VRRP.collect('json'))
    for group in json_data:
        if 'data' in group:
            if 'ifp_ifname' in group['data']:
                iface = group['data']['ifp_ifname']
                state = group['data']['state'] # 2 = Master
                if iface in interfaces and state != 2:
                    interfaces.remove(iface)
    return interfaces

def generate(mdns):
    if not mdns:
        return None

    if 'disable' in mdns:
        print('Warning: mDNS repeater will be deactivated because it is disabled')
        return None

    if mdns['vrrp_exists'] and 'vrrp_disable' in mdns:
        mdns['interface'] = get_vrrp_master(mdns['interface'])

        if len(mdns['interface']) < 2:
            return None

    render(config_file, 'mdns-repeater/avahi-daemon.j2', mdns)
    return None

def apply(mdns):
    if not mdns or 'disable' in mdns:
        call('systemctl stop avahi-daemon.service')
        if os.path.exists(config_file):
            os.unlink(config_file)

        if os.path.exists(vrrp_running_file):
            os.unlink(vrrp_running_file)
    else:
        if 'vrrp_disable' not in mdns and os.path.exists(vrrp_running_file):
            os.unlink(vrrp_running_file)

        if mdns['vrrp_exists'] and 'vrrp_disable' in mdns:
            if not os.path.exists(vrrp_running_file):
                os.mknod(vrrp_running_file) # vrrp script looks for this file to update mdns repeater

            if len(mdns['interface']) < 2:
                call('systemctl stop avahi-daemon.service')
                return None

        call('systemctl restart avahi-daemon.service')

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
