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

from sys import exit

from vyos import ConfigError
from vyos import airbag
from vyos.config import Config
from vyos.logger import syslog
from vyos.template import render_to_string
from vyos.util import read_file, write_file
airbag.enable()

# path to logrotate config for atop
logrotate_atop_file = '/etc/logrotate.d/vyos-atop'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['system', 'logs']
    logs_config = conf.get_config_dict(base)

    return logs_config


def verify(logs_config):
    # Nothing to verify here
    pass


def generate(logs_config):
    # get configuration for logrotate atop
    logrotate_atop = logs_config.get('logs', {}).get('logrotate',
                                                     {}).get('atop', {})
    # read current config file for atop
    logrotate_atop_current = read_file(logrotate_atop_file)
    # generate new config file for atop
    logrotate_atop_new = render_to_string('logs/logrotate/vyos-atop.tmpl',
                                          logrotate_atop)
    # update configuration files if this is necessary
    if logrotate_atop_new != logrotate_atop_current:
        syslog.debug('Adding logrotate config for atop')
        write_file(logrotate_atop_file, logrotate_atop_new)


def apply(logs_config):
    # No further actions needed
    pass


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
