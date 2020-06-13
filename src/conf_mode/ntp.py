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

from copy import deepcopy
from ipaddress import ip_network
from netifaces import interfaces
from sys import exit

from vyos.config import Config
from vyos.util import call
from vyos.template import render
from vyos import ConfigError

from vyos import airbag
airbag.enable()

config_file = r'/etc/ntp.conf'
systemd_override = r'/etc/systemd/system/ntp.service.d/override.conf'

default_config_data = {
    'servers': [],
    'allowed_networks': [],
    'listen_address': [],
    'vrf': ''
}

def get_config():
    ntp = deepcopy(default_config_data)
    conf = Config()
    base = ['system', 'ntp']
    if not conf.exists(base):
        return None
    else:
        conf.set_level(base)

    node = ['allow-clients', 'address']
    if conf.exists(node):
        networks = conf.return_values(node)
        for n in networks:
            addr = ip_network(n)
            net = {
                "network" : n,
                "address" : addr.network_address,
                "netmask" : addr.netmask
            }

            ntp['allowed_networks'].append(net)

    node = ['listen-address']
    if conf.exists(node):
        ntp['listen_address'] = conf.return_values(node)

    node = ['server']
    if conf.exists(node):
        for node in conf.list_nodes(node):
            options = []
            server = {
                "name": node,
                "options": []
            }
            if conf.exists('server {0} noselect'.format(node)):
                options.append('noselect')
            if conf.exists('server {0} preempt'.format(node)):
                options.append('preempt')
            if conf.exists('server {0} prefer'.format(node)):
                options.append('prefer')

            server['options'] = options
            ntp['servers'].append(server)

    node = ['vrf']
    if conf.exists(node):
        ntp['vrf'] = conf.return_value(node)

    return ntp

def verify(ntp):
    # bail out early - looks like removal from running config
    if not ntp:
        return None

    # Configuring allowed clients without a server makes no sense
    if len(ntp['allowed_networks']) and not len(ntp['servers']):
        raise ConfigError('NTP server not configured')

    if ntp['vrf'] and ntp['vrf'] not in interfaces():
        raise ConfigError('VRF "{vrf}" does not exist'.format(**ntp))

    return None

def generate(ntp):
    # bail out early - looks like removal from running config
    if not ntp:
        return None

    render(config_file, 'ntp/ntp.conf.tmpl', ntp)
    render(systemd_override, 'ntp/override.conf.tmpl', ntp, trim_blocks=True)

    return None

def apply(ntp):
    if not ntp:
        # NTP support is removed in the commit
        call('systemctl stop ntp.service')
        if os.path.exists(config_file):
            os.unlink(config_file)
        if os.path.isfile(systemd_override):
            os.unlink(systemd_override)

    # Reload systemd manager configuration
    call('systemctl daemon-reload')

    if ntp:
        call('systemctl restart ntp.service')

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
