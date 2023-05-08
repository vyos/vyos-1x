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
from vyos.configdict import dict_merge
from vyos.util import call
from vyos.template import render
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

rsyslog_conf = '/etc/rsyslog.d/00-vyos.conf'
logrotate_conf = '/etc/logrotate.d/vyos-rsyslog'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'syslog']
    if not conf.exists(base):
        return None

    syslog = conf.get_config_dict(base, key_mangling=('-', '_'),
                                  get_first_key=True, no_tag_node_value_mangle=True)

    syslog.update({ 'logrotate' : logrotate_conf })

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)
    # XXX: some syslog default values can not be merged here (originating from
    # a tagNode - remove and add them later per individual tagNode instance
    if 'console' in default_values:
        del default_values['console']
    for entity in ['global', 'user', 'host', 'file']:
        if entity in default_values:
            del default_values[entity]

    syslog = dict_merge(default_values, syslog)

    # XXX: add defaults for "console" tree
    if 'console' in syslog and 'facility' in syslog['console']:
        default_values = defaults(base + ['console', 'facility'])
        for facility in syslog['console']['facility']:
            syslog['console']['facility'][facility] = dict_merge(default_values,
                                                                syslog['console']['facility'][facility])

    # XXX: add defaults for "host" tree
    if 'host' in syslog:
        default_values_host = defaults(base + ['host'])
        if 'facility' in default_values_host:
            del default_values_host['facility']
        default_values_facility = defaults(base + ['host', 'facility'])

        for host, host_config in syslog['host'].items():
            syslog['host'][host] = dict_merge(default_values_host, syslog['host'][host])
            if 'facility' in host_config:
                for facility in host_config['facility']:
                    syslog['host'][host]['facility'][facility] = dict_merge(default_values_facility,
                                                                        syslog['host'][host]['facility'][facility])

    # XXX: add defaults for "user" tree
    if 'user' in syslog:
        default_values = defaults(base + ['user', 'facility'])
        for user, user_config in syslog['user'].items():
            if 'facility' in user_config:
                for facility in user_config['facility']:
                    syslog['user'][user]['facility'][facility] = dict_merge(default_values,
                                                                        syslog['user'][user]['facility'][facility])

    # XXX: add defaults for "file" tree
    if 'file' in syslog:
        default_values = defaults(base + ['file'])
        for file, file_config in syslog['file'].items():
            for facility in file_config['facility']:
                syslog['file'][file]['facility'][facility] = dict_merge(default_values,
                                                                        syslog['file'][file]['facility'][facility])

    return syslog

def verify(syslog):
    if not syslog:
        return None

def generate(syslog):
    if not syslog:
        if os.path.exists(rsyslog_conf):
            os.path.unlink(rsyslog_conf)
        if os.path.exists(logrotate_conf):
            os.path.unlink(logrotate_conf)

        return None

    render(rsyslog_conf, 'rsyslog/rsyslog.conf.j2', syslog)
    render(logrotate_conf, 'rsyslog/logrotate.j2', syslog)

def apply(syslog):
    systemd_service = 'syslog.service'
    if not syslog:
        call(f'systemctl stop {systemd_service}')
        return None

    call(f'systemctl reload-or-restart {systemd_service}')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
