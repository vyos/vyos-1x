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

from sys import exit

from vyos.config import Config
from vyos.template import render
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = r'/run/fastnetmon/fastnetmon.conf'
networks_list = r'/run/fastnetmon/networks_list'
excluded_networks_list = r'/run/fastnetmon/excluded_networks_list'
attack_dir = '/var/log/fastnetmon_attacks'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'ids', 'ddos-protection']
    if not conf.exists(base):
        return None

    fastnetmon = conf.get_config_dict(base, key_mangling=('-', '_'),
                                      get_first_key=True,
                                      with_recursive_defaults=True)

    return fastnetmon

def verify(fastnetmon):
    if not fastnetmon:
        return None

    if 'mode' not in fastnetmon:
        raise ConfigError('Specify operating mode!')

    if fastnetmon.get('mode') == 'mirror' and 'listen_interface' not in fastnetmon:
        raise ConfigError("Incorrect settings for 'mode mirror': must specify interface(s) for traffic mirroring")

    if fastnetmon.get('mode') == 'sflow' and 'listen_address' not in fastnetmon.get('sflow', {}):
        raise ConfigError("Incorrect settings for 'mode sflow': must specify sFlow 'listen-address'")

    if 'alert_script' in fastnetmon:
        if os.path.isfile(fastnetmon['alert_script']):
            # Check script permissions
            if not os.access(fastnetmon['alert_script'], os.X_OK):
                raise ConfigError('Script "{alert_script}" is not executable!'.format(fastnetmon['alert_script']))
        else:
           raise ConfigError('File "{alert_script}" does not exists!'.format(fastnetmon))

def generate(fastnetmon):
    if not fastnetmon:
        for file in [config_file, networks_list]:
            if os.path.isfile(file):
                os.unlink(file)

        return None

    # Create dir for log attack details
    if not os.path.exists(attack_dir):
        os.mkdir(attack_dir)

    render(config_file, 'ids/fastnetmon.j2', fastnetmon)
    render(networks_list, 'ids/fastnetmon_networks_list.j2', fastnetmon)
    render(excluded_networks_list, 'ids/fastnetmon_excluded_networks_list.j2', fastnetmon)
    return None

def apply(fastnetmon):
    systemd_service = 'fastnetmon.service'
    if not fastnetmon:
        # Stop fastnetmon service if removed
        call(f'systemctl stop {systemd_service}')
    else:
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
