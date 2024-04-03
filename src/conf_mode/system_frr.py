#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
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

from sys import exit

from vyos import ConfigError
from vyos.base import Warning
from vyos.config import Config
from vyos.logger import syslog
from vyos.template import render_to_string
from vyos.utils.boot import boot_configuration_complete
from vyos.utils.file import read_file
from vyos.utils.file import write_file
from vyos.utils.process import call

from vyos import airbag
airbag.enable()

# path to daemons config and config status files
config_file = '/etc/frr/daemons'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['system', 'frr']
    frr_config = conf.get_config_dict(base, key_mangling=('-', '_'),
                                      get_first_key=True,
                                      with_recursive_defaults=True)

    return frr_config

def verify(frr_config):
    # Nothing to verify here
    pass

def generate(frr_config):
    # read daemons config file
    daemons_config_current = read_file(config_file)
    # generate new config file
    daemons_config_new = render_to_string('frr/daemons.frr.tmpl', frr_config)
    # update configuration file if this is necessary
    if daemons_config_new != daemons_config_current:
        syslog.warning('FRR daemons configuration file need to be changed')
        write_file(config_file, daemons_config_new)
        frr_config['config_file_changed'] = True

def apply(frr_config):
    # display warning to user
    if boot_configuration_complete() and frr_config.get('config_file_changed'):
        # Since FRR restart is not safe thing, better to give
        # control over this to users
        Warning('You need to reboot the router (preferred) or restart '\
                'FRR to apply changes in modules settings')

    # restart FRR automatically
    # During initial boot this should be safe in most cases
    if not boot_configuration_complete() and frr_config.get('config_file_changed'):
        syslog.warning('Restarting FRR to apply changes in modules')
        call(f'systemctl restart frr.service')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
