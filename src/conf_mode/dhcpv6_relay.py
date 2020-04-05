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
from copy import deepcopy
from jinja2 import FileSystemLoader, Environment

from vyos.config import Config
from vyos.defaults import directories as vyos_data_dir
from vyos import ConfigError

config_file = r'/etc/default/isc-dhcpv6-relay'

default_config_data = {
    'listen_addr': [],
    'upstream_addr': [],
    'options': [],
}

def get_config():
    relay = deepcopy(default_config_data)
    conf = Config()
    if not conf.exists('service dhcpv6-relay'):
        return None
    else:
        conf.set_level('service dhcpv6-relay')

    # Network interfaces/address to listen on for DHCPv6 query(s)
    if conf.exists('listen-interface'):
        interfaces = conf.list_nodes('listen-interface')
        for intf in interfaces:
            if conf.exists('listen-interface {0} address'.format(intf)):
                addr = conf.return_value('listen-interface {0} address'.format(intf))
                listen = addr + '%' + intf
                relay['listen_addr'].append(listen)

    # Upstream interface/address for remote DHCPv6 server
    if conf.exists('upstream-interface'):
        interfaces = conf.list_nodes('upstream-interface')
        for intf in interfaces:
            addresses = conf.return_values('upstream-interface {0} address'.format(intf))
            for addr in addresses:
                server = addr + '%' + intf
                relay['upstream_addr'].append(server)

    # Maximum hop count. When forwarding packets, dhcrelay discards packets
    # which have reached a hop count of COUNT. Default is 10. Maximum is 255.
    if conf.exists('max-hop-count'):
        count = '-c ' + conf.return_value('max-hop-count')
        relay['options'].append(count)

    if conf.exists('use-interface-id-option'):
        relay['options'].append('-I')

    return relay

def verify(relay):
    # bail out early - looks like removal from running config
    if relay is None:
        return None

    if len(relay['listen_addr']) == 0 or len(relay['upstream_addr']) == 0:
        raise ConfigError('Must set at least one listen and upstream interface addresses.')

    return None

def generate(relay):
    # bail out early - looks like removal from running config
    if relay is None:
        return None

    # Prepare Jinja2 template loader from files
    tmpl_path = os.path.join(vyos_data_dir['data'], 'templates', 'dhcpv6-relay')
    fs_loader = FileSystemLoader(tmpl_path)
    env = Environment(loader=fs_loader)

    tmpl = env.get_template('config.tmpl')
    config_text = tmpl.render(relay)
    with open(config_file, 'w') as f:
        f.write(config_text)

    return None

def apply(relay):
    if relay is not None:
        os.system('sudo systemctl restart isc-dhcpv6-relay.service')
    else:
        # DHCPv6 relay support is removed in the commit
        os.system('sudo systemctl stop isc-dhcpv6-relay.service')
        os.unlink(config_file)

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
