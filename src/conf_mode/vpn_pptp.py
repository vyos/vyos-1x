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

from copy import deepcopy
from socket import socket, AF_INET, SOCK_STREAM
from sys import exit
from time import sleep

from vyos.config import Config
from vyos import ConfigError
from vyos.util import call, get_half_cpus
from vyos.template import render

pptp_conf = '/run/accel-pppd/pptp.conf'
pptp_chap_secrets = '/run/accel-pppd/pptp.chap-secrets'

default_pptp = {
    'authentication': {
        'mode': 'local',
        'local-users': {
        },
        'radiussrv': {},
        'auth_proto': 'auth_mschap_v2',
        'mppe': 'require'
    },
    'chap_secrets_file': pptp_chap_secrets, # used in Jinja2 template
    'outside_addr': '',
    'dns': [],
    'wins': [],
    'client_ip_pool': '',
    'mtu': '1436',
    'thread_cnt': get_half_cpus()
}

def get_config():
    c = Config()
    if not c.exists(['vpn', 'pptp', 'remote-access']):
        return None

    c.set_level(['vpn', 'pptp', 'remote-access'])
    pptp = deepcopy(default_pptp)

    ### general options ###

    if c.exists(['dns-servers', 'server-1']):
        pptp['dns'].append(c.return_value(['dns-servers', 'server-1']))
    if c.exists(['dns-servers', 'server-2']):
        pptp['dns'].append(c.return_value(['dns-servers', 'server-2']))
    if c.exists(['wins-servers', 'server-1']):
        pptp['wins'].append(
            c.return_value(['wins-servers', 'server-1']))
    if c.exists(['wins-servers', 'server-2']):
        pptp['wins'].append(
            c.return_value(['wins-servers', 'server-2']))
    if c.exists(['outside-address']):
        pptp['outside_addr'] = c.return_value(['outside-address'])

    # auth local
    if c.exists(['authentication', 'mode', 'local']):
        if c.exists(['authentication', 'local-users', 'username']):
            for usr in c.list_nodes(['authentication', 'local-users', 'username']):
                pptp['authentication']['local-users'].update(
                    {
                        usr: {
                            'passwd': '',
                            'state': 'enabled',
                            'ip': ''
                        }
                    }
                )

                if c.exists(['authentication', 'local-users', 'username', usr, 'password']):
                    pptp['authentication']['local-users'][usr]['passwd'] = c.return_value(
                        ['authentication', 'local-users', 'username', usr, 'password'])
                if c.exists(['authentication', 'local-users', 'username', usr, 'disable']):
                    pptp['authentication']['local-users'][usr]['state'] = 'disable'
                if c.exists(['authentication', 'local-users', 'username', usr, 'static-ip']):
                    pptp['authentication']['local-users'][usr]['ip'] = c.return_value(
                        ['authentication', 'local-users', 'username', usr, 'static-ip'])

    # authentication mode radius servers and settings

    if c.exists(['authentication', 'mode', 'radius']):
        pptp['authentication']['mode'] = 'radius'
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

            pptp['authentication']['radiussrv'].update(
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
            pptp['client_ip_pool'] = c.return_value(
                ['client-ip-pool', 'start'])
        if c.exists(['client-ip-pool', 'stop']):
            pptp['client_ip_pool'] += '-' + \
                re.search(
                    '[0-9]+$', c.return_value(['client-ip-pool', 'stop'])).group(0)
    if c.exists(['mtu']):
        pptp['mtu'] = c.return_value(['mtu'])

    # gateway address
    if c.exists(['gateway-address']):
        pptp['gw_ip'] = c.return_value(['gateway-address'])
    else:
        pptp['gw_ip'] = re.sub(
            '[0-9]+$', '1', pptp['client_ip_pool'])

    if c.exists(['authentication', 'require']):
        if c.return_value(['authentication', 'require']) == 'pap':
            pptp['authentication']['auth_proto'] = 'auth_pap'
        if c.return_value(['authentication', 'require']) == 'chap':
            pptp['authentication']['auth_proto'] = 'auth_chap_md5'
        if c.return_value(['authentication', 'require']) == 'mschap':
            pptp['authentication']['auth_proto'] = 'auth_mschap_v1'
        if c.return_value(['authentication', 'require']) == 'mschap-v2':
            pptp['authentication']['auth_proto'] = 'auth_mschap_v2'

        if c.exists(['authentication', 'mppe']):
            pptp['authentication']['mppe'] = c.return_value(
                ['authentication', 'mppe'])

    return pptp


def verify(pptp):
    if not pptp:
        return None

    if pptp['authentication']['mode'] == 'local':
        if not pptp['authentication']['local-users']:
            raise ConfigError(
                'pptp-server authentication local-users required')
        for usr in pptp['authentication']['local-users']:
            if not pptp['authentication']['local-users'][usr]['passwd']:
                raise ConfigError('user ' + usr + ' requires a password')

    if pptp['authentication']['mode'] == 'radius':
        if len(pptp['authentication']['radiussrv']) == 0:
            raise ConfigError('radius server required')
        for rsrv in pptp['authentication']['radiussrv']:
            if pptp['authentication']['radiussrv'][rsrv]['secret'] == None:
                raise ConfigError('radius server ' + rsrv +
                                  ' needs a secret configured')


def generate(pptp):
    if not pptp:
        return None

    dirname = os.path.dirname(pptp_conf)
    if not os.path.exists(dirname):
        os.mkdir(dirname)

    render(pptp_conf, 'pptp/pptp.config.tmpl', pptp, trim_blocks=True)

    if pptp['authentication']['local-users']:
        old_umask = os.umask(0o077)
        render(pptp_chap_secrets, 'pptp/chap-secrets.tmpl', pptp, trim_blocks=True)
        os.umask(old_umask)


def apply(pptp):
    if not pptp:
        call('systemctl stop accel-ppp@pptp.service')
        for file in [pptp_conf, pptp_chap_secrets]:
            if os.path.exists(file):
                os.unlink(file)

        return None

    call('systemctl restart accel-ppp@pptp.service')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
