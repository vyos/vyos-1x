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
import re
import subprocess

from jinja2 import FileSystemLoader, Environment
from socket import socket, AF_INET, SOCK_STREAM
from sys import exit
from time import sleep

from vyos.config import Config
from vyos.defaults import directories as vyos_data_dir
from vyos import ConfigError

pidfile = r'/var/run/accel_pptp.pid'
pptp_cnf_dir = r'/etc/accel-ppp/pptp'
chap_secrets = pptp_cnf_dir + '/chap-secrets'
pptp_conf = pptp_cnf_dir + '/pptp.config'

# config path creation
if not os.path.exists(pptp_cnf_dir):
    os.makedirs(pptp_cnf_dir)

def _chk_con():
    cnt = 0
    s = socket(AF_INET, SOCK_STREAM)
    while True:
        try:
            s.connect(("127.0.0.1", 2003))
            break
        except ConnectionRefusedError:
            sleep(0.5)
            cnt += 1
            if cnt == 100:
                raise("failed to start pptp server")
                break

# chap_secrets file if auth mode local

def _accel_cmd(cmd=''):
    if not cmd:
        return None
    try:
        ret = subprocess.check_output(
            ['/usr/bin/accel-cmd', '-p', '2003', cmd]).decode().strip()
        return ret
    except:
        return 1

###
# inline helper functions end
###


def get_config():
    c = Config()
    if not c.exists(['vpn', 'pptp', 'remote-access']):
        return None

    c.set_level(['vpn', 'pptp', 'remote-access'])
    config_data = {
        'authentication': {
            'mode': 'local',
            'local-users': {
            },
            'radiussrv': {},
            'auth_proto': 'auth_mschap_v2',
            'mppe': 'require'
        },
        'outside_addr': '',
        'dns': [],
        'wins': [],
        'client_ip_pool': '',
        'mtu': '1436',
    }

    ### general options ###

    if c.exists(['dns-servers', 'server-1']):
        config_data['dns'].append(c.return_value(['dns-servers', 'server-1']))
    if c.exists(['dns-servers', 'server-2']):
        config_data['dns'].append(c.return_value(['dns-servers', 'server-2']))
    if c.exists(['wins-servers', 'server-1']):
        config_data['wins'].append(
            c.return_value(['wins-servers', 'server-1']))
    if c.exists(['wins-servers', 'server-2']):
        config_data['wins'].append(
            c.return_value(['wins-servers', 'server-2']))
    if c.exists(['outside-address']):
        config_data['outside_addr'] = c.return_value(['outside-address'])

    # auth local
    if c.exists(['authentication', 'mode', 'local']):
        if c.exists(['authentication', 'local-users', 'username']):
            for usr in c.list_nodes(['authentication', 'local-users', 'username']):
                config_data['authentication']['local-users'].update(
                    {
                        usr: {
                            'passwd': '',
                            'state': 'enabled',
                            'ip': ''
                        }
                    }
                )

                if c.exists(['authentication', 'local-users', 'username', usr, 'password']):
                    config_data['authentication']['local-users'][usr]['passwd'] = c.return_value(
                        ['authentication', 'local-users', 'username', usr, 'password'])
                if c.exists(['authentication', 'local-users', 'username', usr, 'disable']):
                    config_data['authentication']['local-users'][usr]['state'] = 'disable'
                if c.exists(['authentication', 'local-users', 'username', usr, 'static-ip']):
                    config_data['authentication']['local-users'][usr]['ip'] = c.return_value(
                        ['authentication', 'local-users', 'username', usr, 'static-ip'])

    # authentication mode radius servers and settings

    if c.exists(['authentication', 'mode', 'radius']):
        config_data['authentication']['mode'] = 'radius'
        rsrvs = c.list_nodes(['authentication', 'radius', 'server'])
        for rsrv in rsrvs:
            if not c.return_value(['authentication', 'radius', 'server', rsrv, 'fail-time']):
                ftime = '0'
            else:
                ftime = c.return_value(
                    ['authentication', 'radius', 'server', rsrv, 'fail-time'])
            if not c.return_value(['authentication', 'radius-server', rsrv, 'req-limit']):
                reql = '0'
            else:
                reql = c.return_value(
                    ['authentication', 'radius', 'server', rsrv, 'req-limit'])

            config_data['authentication']['radiussrv'].update(
                {
                    rsrv: {
                        'secret': c.return_value(['authentication', 'radius', 'server', rsrv, 'key']),
                        'fail-time': ftime,
                        'req-limit': reql
                    }
                }
            )

    if c.exists(['client-ip-pool']):
        if c.exists(['client-ip-pool', 'start']):
            config_data['client_ip_pool'] = c.return_value(
                ['client-ip-pool', 'start'])
        if c.exists(['client-ip-pool', 'stop']):
            config_data['client_ip_pool'] += '-' + \
                re.search(
                    '[0-9]+$', c.return_value(['client-ip-pool', 'stop'])).group(0)
    if c.exists(['mtu']):
        config_data['mtu'] = c.return_value(['mtu'])

    # gateway address
    if c.exists(['gateway-address']):
        config_data['gw_ip'] = c.return_value(['gateway-address'])
    else:
        config_data['gw_ip'] = re.sub(
            '[0-9]+$', '1', config_data['client_ip_pool'])

    if c.exists(['authentication', 'require']):
        if c.return_value(['authentication', 'require']) == 'pap':
            config_data['authentication']['auth_proto'] = 'auth_pap'
        if c.return_value(['authentication', 'require']) == 'chap':
            config_data['authentication']['auth_proto'] = 'auth_chap_md5'
        if c.return_value(['authentication', 'require']) == 'mschap':
            config_data['authentication']['auth_proto'] = 'auth_mschap_v1'
        if c.return_value(['authentication', 'require']) == 'mschap-v2':
            config_data['authentication']['auth_proto'] = 'auth_mschap_v2'

        if c.exists(['authentication', 'mppe']):
            config_data['authentication']['mppe'] = c.return_value(
                ['authentication', 'mppe'])

    return config_data


def verify(c):
    if c == None:
        return None

    if c['authentication']['mode'] == 'local':
        if not c['authentication']['local-users']:
            raise ConfigError(
                'pptp-server authentication local-users required')
        for usr in c['authentication']['local-users']:
            if not c['authentication']['local-users'][usr]['passwd']:
                raise ConfigError('user ' + usr + ' requires a password')

    if c['authentication']['mode'] == 'radius':
        if len(c['authentication']['radiussrv']) == 0:
            raise ConfigError('radius server required')
        for rsrv in c['authentication']['radiussrv']:
            if c['authentication']['radiussrv'][rsrv]['secret'] == None:
                raise ConfigError('radius server ' + rsrv +
                                  ' needs a secret configured')


def generate(c):
    if c == None:
        return None

    # Prepare Jinja2 template loader from files
    tmpl_path = os.path.join(vyos_data_dir['data'], 'templates', 'pptp')
    fs_loader = FileSystemLoader(tmpl_path)
    env = Environment(loader=fs_loader, trim_blocks=True)

    # accel-cmd reload doesn't work so any change results in a restart of the daemon
    try:
        if os.cpu_count() == 1:
            c['thread_cnt'] = 1
        else:
            c['thread_cnt'] = int(os.cpu_count()/2)
    except KeyError:
        if os.cpu_count() == 1:
            c['thread_cnt'] = 1
        else:
            c['thread_cnt'] = int(os.cpu_count()/2)

    tmpl = env.get_template('pptp.config.tmpl')
    config_text = tmpl.render(c)
    with open(pptp_conf, 'w') as f:
        f.write(config_text)

    if c['authentication']['local-users']:
        tmpl = env.get_template('chap-secrets.tmpl')
        chap_secrets_txt = tmpl.render(c)
        old_umask = os.umask(0o077)
        with open(chap_secrets, 'w') as f:
            f.write(chap_secrets_txt)
        os.umask(old_umask)

    return c


def apply(c):
    if c == None:
        if os.path.exists(pidfile):
            _accel_cmd('shutdown hard')
            if os.path.exists(pidfile):
                os.remove(pidfile)
        return None

    if not os.path.exists(pidfile):
        ret = subprocess.call(
            ['/usr/sbin/accel-pppd', '-c', pptp_conf, '-p', pidfile, '-d'])
        _chk_con()
        if ret != 0 and os.path.exists(pidfile):
            os.remove(pidfile)
            raise ConfigError('accel-pppd failed to start')
    else:
        # if gw ip changes, only restart doesn't work
        _accel_cmd('restart')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
