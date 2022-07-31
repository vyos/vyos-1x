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
from vyos.base import Warning
from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.template import render
from vyos.util import call
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = r'/run/radvd/radvd.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'router-advert']
    rtradv = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_interface_values = defaults(base + ['interface'])
    # we deal with prefix, route defaults later on
    if 'prefix' in default_interface_values:
        del default_interface_values['prefix']
    if 'route' in default_interface_values:
        del default_interface_values['route']

    default_prefix_values = defaults(base + ['interface', 'prefix'])
    default_route_values = defaults(base + ['interface', 'route'])

    if 'interface' in rtradv:
        for interface in rtradv['interface']:
            rtradv['interface'][interface] = dict_merge(
                default_interface_values, rtradv['interface'][interface])

            if 'prefix' in rtradv['interface'][interface]:
                for prefix in rtradv['interface'][interface]['prefix']:
                    rtradv['interface'][interface]['prefix'][prefix] = dict_merge(
                        default_prefix_values, rtradv['interface'][interface]['prefix'][prefix])

            if 'route' in rtradv['interface'][interface]:
                for route in rtradv['interface'][interface]['route']:
                    rtradv['interface'][interface]['route'][route] = dict_merge(
                        default_route_values, rtradv['interface'][interface]['route'][route])

            if 'name_server' in rtradv['interface'][interface]:
                # always use a list when dealing with nameservers - eases the template generation
                if isinstance(rtradv['interface'][interface]['name_server'], str):
                    rtradv['interface'][interface]['name_server'] = [
                        rtradv['interface'][interface]['name_server']]

    return rtradv

def verify(rtradv):
    if not rtradv:
        return None

    if 'interface' not in rtradv:
        return None

    for interface, interface_config in rtradv['interface'].items():
        if 'prefix' in interface:
            for prefix, prefix_config in interface_config['prefix'].items():
                valid_lifetime = prefix_config['valid_lifetime']
                if valid_lifetime == 'infinity':
                    valid_lifetime = 4294967295

                preferred_lifetime = prefix_config['preferred_lifetime']
                if preferred_lifetime == 'infinity':
                    preferred_lifetime = 4294967295

                if not (int(valid_lifetime) >= int(preferred_lifetime)):
                    raise ConfigError('Prefix valid-lifetime must be greater then or equal to preferred-lifetime')

        if 'name_server_lifetime' in interface_config:
            # man page states:
            # The maximum duration how long the RDNSS entries are used for name
            # resolution. A value of 0 means the nameserver must no longer be
            # used. The value, if not 0, must be at least MaxRtrAdvInterval. To
            # ensure stale RDNSS info gets removed in a timely fashion, this
            # should not be greater than 2*MaxRtrAdvInterval.
            lifetime = int(interface_config['name_server_lifetime'])
            interval_max = int(interface_config['interval']['max'])
            if lifetime > 0:
                if lifetime < int(interval_max):
                    raise ConfigError(f'RDNSS lifetime must be at least "{interval_max}" seconds!')
                if lifetime > 2* interval_max:
                    Warning(f'RDNSS lifetime should not exceed "{2 * interval_max}" which is two times "interval max"!')

    return None

def generate(rtradv):
    if not rtradv:
        return None

    render(config_file, 'router-advert/radvd.conf.j2', rtradv, permission=0o644)
    return None

def apply(rtradv):
    systemd_service = 'radvd.service'
    if not rtradv:
        # bail out early - looks like removal from running config
        call(f'systemctl stop {systemd_service}')
        if os.path.exists(config_file):
            os.unlink(config_file)

        return None

    call(f'systemctl reload-or-restart {systemd_service}')

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
