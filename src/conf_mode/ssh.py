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

config_file = r'/etc/ssh/sshd_config'

default_config_data = {
    'port' : '22',
    'log_level': 'INFO',
    'password_authentication': 'yes',
    'host_validation': 'yes'
}

def get_config():
    ssh = default_config_data
    conf = Config()
    base = ['service', 'ssh']
    if not conf.exists(base):
        return None
    else:
        conf.set_level(base)

    tmp = ['access-control', 'allow', 'user']
    if conf.exists(tmp):
        ssh['allow_users'] = conf.return_values(tmp)

    tmp = ['access-control', 'allow', 'group']
    if conf.exists(tmp):
        ssh['allow_groups'] = conf.return_values(tmp)

    tmp = ['access-control', 'deny' 'user']
    if conf.exists(tmp):
        ssh['deny_users'] = conf.return_values(tmp)

    tmp = ['access-control', 'deny', 'group']
    if conf.exists(tmp):
        ssh['deny_groups'] = conf.return_values(tmp)

    tmp = ['ciphers']
    if conf.exists(tmp):
        ssh['ciphers'] = conf.return_values(tmp)

    tmp = ['key-exchange']
    if conf.exists(tmp):
        ssh['key_exchange'] = conf.return_values(tmp)

    if conf.exists(['disable-host-validation']):
        ssh['host_validation'] = 'no'

    if conf.exists(['disable-password-authentication']):
        ssh['password_authentication'] = 'no'

    tmp = ['listen-address']
    if conf.exists(tmp):
        # We can listen on both IPv4 and IPv6 addresses
        # Maybe there could be a check in the future if the configured IP address
        # is configured on this system at all?
        ssh['listen_on'] = conf.return_values(tmp)

    tmp = ['loglevel']
    if conf.exists(tmp):
        ssh['log_level'] = conf.return_value(tmp)

    tmp = ['mac']
    if conf.exists(tmp):
        ssh['mac'] = conf.return_values(tmp)

    tmp = ['port']
    if conf.exists(tmp):
        ssh['port'] = conf.return_values(tmp)

    tmp = ['client-keepalive-interval']
    if conf.exists(tmp):
        ssh['client_keepalive'] = conf.return_value(tmp)


    return ssh

def verify(ssh):
    if not ssh:
        return None

    if 'loglevel' in ssh.keys():
        allowed_loglevel = 'QUIET, FATAL, ERROR, INFO, VERBOSE'
        if not ssh['loglevel'] in allowed_loglevel:
            raise ConfigError('loglevel must be one of "{0}"\n'.format(allowed_loglevel))

    return None

def generate(ssh):
    if not ssh:
        return None

    render(config_file, 'ssh/sshd_config.tmpl', ssh, trim_blocks=True)
    return None

def apply(ssh):
    if not ssh:
        # SSH access is removed in the commit
        call('systemctl stop ssh.service')
        if os.path.isfile(config_file):
            os.unlink(config_file)
    else:
        call('systemctl restart ssh.service')

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
