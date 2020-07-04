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
from vyos import ConfigError
from vyos.util import call
from vyos.template import render
from vyos import airbag
airbag.enable()

config_file = r'/etc/fastnetmon.conf'
networks_list = r'/etc/networks_list'

def get_config():
    conf = Config()
    base = ['service', 'ids', 'ddos-protection']
    fastnetmon = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    return fastnetmon

def verify(fastnetmon):
    if not fastnetmon:
        return None

    if not "mode" in fastnetmon:
        raise ConfigError('ddos-protection mode is mandatory!')

    if not "network" in fastnetmon:
        raise ConfigError('Required define network!')

    if not "listen_interface" in fastnetmon:
        raise ConfigError('Define listen-interface is mandatory!')

    if "alert_script" in fastnetmon:
        if os.path.isfile(fastnetmon["alert_script"]):
            # Check script permissions
            if not os.access(fastnetmon["alert_script"], os.X_OK):
                raise ConfigError('Script {0} does not have permissions for execution'.format(fastnetmon["alert_script"]))
        else:
           raise ConfigError('File {0} does not exists!'.format(fastnetmon["alert_script"])) 

def generate(fastnetmon):
    if not fastnetmon:
        if os.path.isfile(config_file):
            os.unlink(config_file)
        if os.path.isfile(networks_list):
            os.unlink(networks_list)

        return

    render(config_file, 'ids/fastnetmon.tmpl', fastnetmon, trim_blocks=True)
    render(networks_list, 'ids/fastnetmon_networks_list.tmpl', fastnetmon, trim_blocks=True)

    return None

def apply(fastnetmon):
    if not fastnetmon:
        # Stop fastnetmon service if removed
        call('systemctl stop fastnetmon.service')
    else:
        call('systemctl restart fastnetmon.service')

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
