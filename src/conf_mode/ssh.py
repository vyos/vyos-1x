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
from jinja2 import FileSystemLoader, Environment
from sys import exit

from vyos.config import Config
from vyos.defaults import directories as vyos_data_dir
from vyos import ConfigError

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
    if not conf.exists('service ssh'):
        return None
    else:
        conf.set_level('service ssh')

    if conf.exists('access-control allow user'):
        allow_users = conf.return_values('access-control allow user')
        ssh['allow_users'] = allow_users

    if conf.exists('access-control allow group'):
        allow_groups = conf.return_values('access-control allow group')
        ssh['allow_groups'] = allow_groups

    if conf.exists('access-control deny user'):
        deny_users = conf.return_values('access-control deny user')
        ssh['deny_users'] = deny_users

    if conf.exists('access-control deny group'):
        deny_groups = conf.return_values('access-control deny group')
        ssh['deny_groups'] =  deny_groups

    if conf.exists('ciphers'):
        ciphers = conf.return_values('ciphers')
        ssh['ciphers'] =  ciphers

    if conf.exists('disable-host-validation'):
        ssh['host_validation'] = 'no'

    if conf.exists('disable-password-authentication'):
        ssh['password_authentication'] = 'no'

    if conf.exists('key-exchange'):
        kex = conf.return_values('key-exchange')
        ssh['key_exchange'] = kex

    if conf.exists('listen-address'):
        # We can listen on both IPv4 and IPv6 addresses
        # Maybe there could be a check in the future if the configured IP address
        # is configured on this system at all?
        addresses = conf.return_values('listen-address')
        listen = []

        for addr in addresses:
            listen.append(addr)

        ssh['listen_on'] = listen

    if conf.exists('loglevel'):
        ssh['log_level'] = conf.return_value('loglevel')

    if conf.exists('mac'):
        mac = conf.return_values('mac')
        ssh['mac'] = mac

    if conf.exists('port'):
        ports = conf.return_values('port')
        mport = []

        for prt in ports:
            mport.append(prt)

        ssh['mport'] = mport

    if conf.exists('client-keepalive-interval'):
        client_keepalive = conf.return_value('client-keepalive-interval')
        ssh['client_keepalive'] = client_keepalive

    return ssh

def verify(ssh):
    if ssh is None:
        return None

    if 'loglevel' in ssh.keys():
        allowed_loglevel = 'QUIET, FATAL, ERROR, INFO, VERBOSE'
        if not ssh['loglevel'] in allowed_loglevel:
            raise ConfigError('loglevel must be one of "{0}"\n'.format(allowed_loglevel))

    return None

def generate(ssh):
    if ssh is None:
        return None

    # Prepare Jinja2 template loader from files
    tmpl_path = os.path.join(vyos_data_dir['data'], 'templates', 'ssh')
    fs_loader = FileSystemLoader(tmpl_path)
    env = Environment(loader=fs_loader)

    tmpl = env.get_template('sshd_config.tmpl')
    config_text = tmpl.render(ssh)
    with open(config_file, 'w') as f:
        f.write(config_text)
    return None

def apply(ssh):
    if ssh is not None and 'port' in ssh.keys():
        os.system("sudo systemctl restart ssh.service")
    else:
        # SSH access is removed in the commit
        os.system("sudo systemctl stop ssh.service")
        if os.path.isfile(config_file):
            os.unlink(config_file)

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
