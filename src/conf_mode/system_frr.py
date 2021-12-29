#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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

from pathlib import Path
from sys import exit

from vyos import ConfigError
from vyos import airbag
from vyos.config import Config
from vyos.logger import syslog
from vyos.template import render_to_string
from vyos.util import read_file, write_file, run
airbag.enable()

# path to daemons config and config status files
config_file = '/etc/frr/daemons'
vyos_status_file = '/tmp/vyos-config-status'
# path to watchfrr for FRR control
watchfrr = '/usr/lib/frr/watchfrr.sh'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['system', 'frr']
    frr_config = conf.get_config_dict(base, get_first_key=True)

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
    # check if this is initial commit during boot or intiated by CLI
    # if the file exists, this must be CLI commit
    commit_type_cli = Path(vyos_status_file).exists()
    # display warning to user
    if commit_type_cli and frr_config.get('config_file_changed'):
        # Since FRR restart is not safe thing, better to give
        # control over this to users
        print('''
        You need to reboot a router (preferred) or restart FRR
        to apply changes in modules settings
        ''')
    # restart FRR automatically. DUring the initial boot this should be
    # safe in most cases
    if not commit_type_cli and frr_config.get('config_file_changed'):
        syslog.warning('Restarting FRR to apply changes in modules')
        run(f'{watchfrr} restart')


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
