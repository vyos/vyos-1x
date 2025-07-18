#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
from vyos.configverify import verify_vrf
from vyos.defaults import systemd_services
from vyos.utils.network import is_addr_assigned
from vyos.utils.process import call
from vyos.template import render
from vyos.template import is_ipv4
from vyos.template import is_ipv6
from vyos import ConfigError
from vyos import airbag
airbag.enable()

rsyslog_conf = '/run/rsyslog/rsyslog.conf'
logrotate_conf = '/etc/logrotate.d/vyos-rsyslog'

systemd_socket = 'syslog.socket'
systemd_service = systemd_services['syslog']

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

    syslog = conf.merge_defaults(syslog, recursive=True)
    if syslog.from_defaults(['local']):
        del syslog['local']

    if 'preserve_fqdn' in syslog:
        if conf.exists(['system', 'host-name']):
            tmp = conf.return_value(['system', 'host-name'])
            syslog['preserve_fqdn']['host_name'] = tmp
        if conf.exists(['system', 'domain-name']):
            tmp  = conf.return_value(['system', 'domain-name'])
            syslog['preserve_fqdn']['domain_name'] = tmp

    return syslog

def verify(syslog):
    if not syslog:
        return None

    if 'preserve_fqdn' in syslog:
        if 'host_name' not in syslog['preserve_fqdn']:
            Warning('No "system host-name" defined - cannot set syslog FQDN!')
        if 'domain_name' not in syslog['preserve_fqdn']:
            Warning('No "system domain-name" defined - cannot set syslog FQDN!')

    if 'remote' in syslog:
        for remote, remote_options in syslog['remote'].items():
            if 'protocol' in remote_options and remote_options['protocol'] == 'udp':
                if 'format' in remote_options and 'octet_counted' in remote_options['format']:
                    Warning(f'Syslog UDP transport for "{remote}" should not use octet-counted format!')

            if 'vrf' in remote_options:
                verify_vrf(remote_options)

            if 'source_address' in remote_options:
                vrf = None
                if 'vrf' in remote_options:
                    vrf = remote_options['vrf']
                if not is_addr_assigned(remote_options['source_address'], vrf):
                    raise ConfigError('No interface with given address specified!')

                source_address = remote_options['source_address']
                if ((is_ipv4(remote) and is_ipv6(source_address)) or
                    (is_ipv6(remote) and is_ipv4(source_address))):
                    raise ConfigError(f'Source-address "{source_address}" does not match '\
                                      f'address-family of remote "{remote}"!')

def generate(syslog):
    if not syslog:
        if os.path.exists(rsyslog_conf):
            os.unlink(rsyslog_conf)
        if os.path.exists(logrotate_conf):
            os.unlink(logrotate_conf)

        return None

    render(rsyslog_conf, 'rsyslog/rsyslog.conf.j2', syslog)
    render(logrotate_conf, 'rsyslog/logrotate.j2', syslog)
    return None

def apply(syslog):
    if not syslog:
        call(f'systemctl stop {systemd_service} {systemd_socket}')
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
