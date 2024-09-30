#!/usr/bin/env python3
#
# Copyright (C) 2018-2024 VyOS maintainers and contributors
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
from vyos.configdict import is_node_changed
from vyos.configverify import verify_vrf
from vyos.utils.process import call
from vyos.template import render
from vyos import ConfigError
from vyos import airbag
airbag.enable()

rsyslog_conf = '/etc/rsyslog.d/00-vyos.conf'
logrotate_conf = '/etc/logrotate.d/vyos-rsyslog'
systemd_override = r'/run/systemd/system/rsyslog.service.d/override.conf'

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

    tmp = is_node_changed(conf, base + ['vrf'])
    if tmp: syslog.update({'restart_required': {}})

    syslog = conf.merge_defaults(syslog, recursive=True)
    if syslog.from_defaults(['global']):
        del syslog['global']

    if (
        'global' in syslog
        and 'preserve_fqdn' in syslog['global']
        and conf.exists(['system', 'host-name'])
        and conf.exists(['system', 'domain-name'])
    ):
        hostname = conf.return_value(['system', 'host-name'])
        domain = conf.return_value(['system', 'domain-name'])
        fqdn = f'{hostname}.{domain}'
        syslog['global']['local_host_name'] = fqdn

    return syslog

def verify(syslog):
    if not syslog:
        return None

    if 'host' in syslog:
         for host, host_options in syslog['host'].items():
             if 'protocol' in host_options and host_options['protocol'] == 'udp':
                 if 'format' in host_options and 'octet_counted' in host_options['format']:
                     Warning(f'Syslog UDP transport for "{host}" should not use octet-counted format!')

    verify_vrf(syslog)

def generate(syslog):
    if not syslog:
        if os.path.exists(rsyslog_conf):
            os.unlink(rsyslog_conf)
        if os.path.exists(logrotate_conf):
            os.unlink(logrotate_conf)

        return None

    render(rsyslog_conf, 'rsyslog/rsyslog.conf.j2', syslog)
    render(systemd_override, 'rsyslog/override.conf.j2', syslog)
    render(logrotate_conf, 'rsyslog/logrotate.j2', syslog)

    # Reload systemd manager configuration
    call('systemctl daemon-reload')
    return None

def apply(syslog):
    systemd_socket = 'syslog.socket'
    systemd_service = 'syslog.service'
    if not syslog:
        call(f'systemctl stop {systemd_service} {systemd_socket}')
        return None

    # we need to restart the service if e.g. the VRF name changed
    systemd_action = 'reload-or-restart'
    if 'restart_required' in syslog:
        systemd_action = 'restart'

    call(f'systemctl {systemd_action} {systemd_service}')
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
