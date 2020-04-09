#!/usr/bin/env python3
#
# Copyright (C) 2017-2020 VyOS maintainers and contributors
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
import fnmatch

from sys import exit
from copy import deepcopy
from jinja2 import FileSystemLoader, Environment

from vyos.config import Config
from vyos.defaults import directories as vyos_data_dir
from vyos import ConfigError
from vyos.util import call

config_file = r'/etc/default/udp-broadcast-relay'

default_config_data = {
    'disabled': False,
    'instances': []
}

def get_config():
    relay = deepcopy(default_config_data)
    conf = Config()
    base = ['service', 'broadcast-relay']

    if not conf.exists(base):
        return None
    else:
        conf.set_level(base)

    # Service can be disabled by user
    if conf.exists('disable'):
        relay['disabled'] = True
        return relay

    # Parse configuration of each individual instance
    if conf.exists('id'):
        for id in conf.list_nodes('id'):
            conf.set_level(base + ['id', id])
            config = {
                'id': id,
                'disabled': False,
                'address': '',
                'description': '',
                'interfaces': [],
                'port': ''
            }

            # Check if individual broadcast relay service is disabled
            if conf.exists(['disable']):
                config['disabled'] = True

            # Source IP of forwarded packets, if empty original senders address is used
            if conf.exists(['address']):
                config['address'] = conf.return_value(['address'])

            # A description for each individual broadcast relay service
            if conf.exists(['description']):
                config['description'] = conf.return_value(['description'])

            # UDP port to listen on for broadcast frames
            if conf.exists(['port']):
                config['port'] = conf.return_value(['port'])

            # Network interfaces to listen on for broadcast frames to be relayed
            if conf.exists(['interface']):
                config['interfaces'] = conf.return_values(['interface'])

            relay['instances'].append(config)

    return relay

def verify(relay):
    if relay is None:
        return None

    if relay['disabled']:
        return None

    for r in relay['instances']:
        # we don't have to check this instance when it's disabled
        if r['disabled']:
            continue

        # we certainly require a UDP port to listen to
        if not r['port']:
            raise ConfigError('UDP broadcast relay "{0}" requires a port number'.format(r['id']))

        # Relaying data without two interface is kinda senseless ...
        if len(r['interfaces']) < 2:
            raise ConfigError('UDP broadcast relay "id {0}" requires at least 2 interfaces'.format(r['id']))

    return None


def generate(relay):
    if relay is None:
        return None

    # Prepare Jinja2 template loader from files
    tmpl_path = os.path.join(vyos_data_dir['data'], 'templates', 'bcast-relay')
    fs_loader = FileSystemLoader(tmpl_path)
    env = Environment(loader=fs_loader)

    config_dir = os.path.dirname(config_file)
    config_filename = os.path.basename(config_file)
    active_configs = []

    for config in fnmatch.filter(os.listdir(config_dir), config_filename + '*'):
        # determine prefix length to identify service instance
        prefix_len = len(config_filename)
        active_configs.append(config[prefix_len:])

    # sort our list
    active_configs.sort()

    # delete old configuration files
    for id in active_configs[:]:
        if os.path.exists(config_file + id):
            os.unlink(config_file + id)

    # If the service is disabled, we can bail out here
    if relay['disabled']:
        print('Warning: UDP broadcast relay service will be deactivated because it is disabled')
        return None

    for r in relay['instances']:
        # Skip writing instance config when it's disabled
        if r['disabled']:
            continue

        # configuration filename contains instance id
        file = config_file + str(r['id'])
        tmpl = env.get_template('udp-broadcast-relay.tmpl')
        config_text = tmpl.render(r)
        with open(file, 'w') as f:
            f.write(config_text)

    return None

def apply(relay):
    # first stop all running services
    call('sudo systemctl stop udp-broadcast-relay@{1..99}')

    if (relay is None) or relay['disabled']:
        return None

    # start only required service instances
    for r in relay['instances']:
        # Don't start individual instance when it's disabled
        if r['disabled']:
            continue
        call('sudo systemctl start udp-broadcast-relay@{0}'.format(r['id']))

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
