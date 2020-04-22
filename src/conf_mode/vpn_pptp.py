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
from stat import S_IRUSR, S_IWUSR, S_IRGRP
from sys import exit

from vyos.config import Config
from vyos.template import render
from vyos.util import call, get_half_cpus
from vyos import ConfigError

pptp_conf = '/run/accel-pppd/pptp.conf'
pptp_chap_secrets = '/run/accel-pppd/pptp.chap-secrets'

default_pptp = {
    'auth_mode' : 'local',
    'local_users' : [],
    'radius_server' : [],
    'radius_acct_tmo' : '30',
    'radius_max_try' : '3',
    'radius_timeout' : '30',
    'radius_nas_id' : '',
    'radius_nas_ip' : '',
    'radius_source_address' : '',
    'radius_shaper_attr' : '',
    'radius_shaper_vendor': '',
    'radius_dynamic_author' : '',
    'chap_secrets_file': pptp_chap_secrets, # used in Jinja2 template
    'outside_addr': '',
    'dnsv4': [],
    'wins': [],
    'client_ip_pool': '',
    'mtu': '1436',
    'auth_proto' : ['auth_mschap_v2'],
    'ppp_mppe' : 'prefer',
    'thread_cnt': get_half_cpus()
}

def get_config():
    conf = Config()
    base_path = ['vpn', 'pptp', 'remote-access']
    if not conf.exists(base_path):
        return None

    pptp = deepcopy(default_pptp)
    conf.set_level(base_path)

    for server in ['server-1', 'server-2']:
        if conf.exists(['dns-servers', server]):
            tmp = conf.return_value(['dns-servers', server])
            pptp['dnsv4'].append(tmp)

    for server in ['server-1', 'server-2']:
        if conf.exists(['wins-servers', server]):
            tmp = conf.return_value(['wins-servers', server])
            pptp['wins'].append(tmp)

    if conf.exists(['outside-address']):
        pptp['outside_addr'] = conf.return_value(['outside-address'])

    if conf.exists(['authentication', 'mode']):
        pptp['auth_mode'] = conf.return_value(['authentication', 'mode'])

    #
    # local auth
    if conf.exists(['authentication', 'local-users']):
        for username in conf.list_nodes(['authentication', 'local-users', 'username']):
            user = {
                'name': username,
                'password' : '',
                'state' : 'enabled',
                'ip' : '*',
            }

            conf.set_level(base_path + ['authentication', 'local-users', 'username', username])

            if conf.exists(['password']):
                user['password'] = conf.return_value(['password'])

            if conf.exists(['disable']):
                user['state'] = 'disable'

            if conf.exists(['static-ip']):
                user['ip'] = conf.return_value(['static-ip'])

            if not conf.exists(['disable']):
                pptp['local_users'].append(user)

    #
    # RADIUS auth and settings
    conf.set_level(base_path + ['authentication', 'radius'])
    if conf.exists(['server']):
        for server in conf.list_nodes(['server']):
            radius = {
                'server' : server,
                'key' : '',
                'fail_time' : 0,
                'port' : '1812'
            }

            conf.set_level(base_path + ['authentication', 'radius', 'server', server])

            if conf.exists(['fail-time']):
                radius['fail-time'] = conf.return_value(['fail-time'])

            if conf.exists(['port']):
                radius['port'] = conf.return_value(['port'])

            if conf.exists(['secret']):
                radius['key'] = conf.return_value(['secret'])

            if not conf.exists(['disable']):
                pptp['radius_server'].append(radius)

        #
        # advanced radius-setting
        conf.set_level(base_path + ['authentication', 'radius'])

        if conf.exists(['acct-timeout']):
            pptp['radius_acct_tmo'] = conf.return_value(['acct-timeout'])

        if conf.exists(['max-try']):
            pptp['radius_max_try'] = conf.return_value(['max-try'])

        if conf.exists(['timeout']):
            pptp['radius_timeout'] = conf.return_value(['timeout'])

        if conf.exists(['nas-identifier']):
            pptp['radius_nas_id'] = conf.return_value(['nas-identifier'])

        if conf.exists(['nas-ip-address']):
            pptp['radius_nas_ip'] = conf.return_value(['nas-ip-address'])

        if conf.exists(['source-address']):
            pptp['radius_source_address'] = conf.return_value(['source-address'])

        # Dynamic Authorization Extensions (DOA)/Change Of Authentication (COA)
        if conf.exists(['dae-server']):
            dae = {
                'port' : '',
                'server' : '',
                'key' : ''
            }

            if conf.exists(['dynamic-author', 'ip-address']):
                dae['server'] = conf.return_value(['dynamic-author', 'ip-address'])

            if conf.exists(['dynamic-author', 'port']):
                dae['port'] = conf.return_value(['dynamic-author', 'port'])

            if conf.exists(['dynamic-author', 'secret']):
                dae['key'] = conf.return_value(['dynamic-author', 'secret'])

            pptp['radius_dynamic_author'] = dae

        if conf.exists(['rate-limit', 'enable']):
            pptp['radius_shaper_attr'] = 'Filter-Id'
            c_attr = ['rate-limit', 'enable', 'attribute']
            if conf.exists(c_attr):
                pptp['radius_shaper_attr'] = conf.return_value(c_attr)

            c_vendor = ['rate-limit', 'enable', 'vendor']
            if conf.exists(c_vendor):
                pptp['radius_shaper_vendor'] = conf.return_value(c_vendor)

    conf.set_level(base_path)
    if conf.exists(['client-ip-pool']):
        if conf.exists(['client-ip-pool', 'start']) and conf.exists(['client-ip-pool', 'stop']):
            start = conf.return_value(['client-ip-pool', 'start'])
            stop  = conf.return_value(['client-ip-pool', 'stop'])
            pptp['client_ip_pool'] = start + '-' + re.search('[0-9]+$', stop).group(0)

    if conf.exists(['mtu']):
        pptp['mtu'] = conf.return_value(['mtu'])

    # gateway address
    if conf.exists(['gateway-address']):
        pptp['gw_ip'] = conf.return_value(['gateway-address'])
    else:
        # calculate gw-ip-address
        if conf.exists(['client-ip-pool', 'start']):
            # use start ip as gw-ip-address
            pptp['gateway_address'] = conf.return_value(['client-ip-pool', 'start'])

    if conf.exists(['authentication', 'require']):
        # clear default list content, now populate with actual CLI values
        pptp['auth_proto'] = []
        auth_mods = {
            'pap': 'auth_pap',
            'chap': 'auth_chap_md5',
            'mschap': 'auth_mschap_v1',
            'mschap-v2': 'auth_mschap_v2'
        }

        for proto in conf.return_values(['authentication', 'require']):
            pptp['auth_proto'].append(auth_mods[proto])

    if conf.exists(['authentication', 'mppe']):
        pptp['ppp_mppe'] = conf.return_value(['authentication', 'mppe'])

    return pptp


def verify(pptp):
    if not pptp:
        return None

    if pptp['auth_mode'] == 'local':
        if not pptp['local_users']:
            raise ConfigError('PPTP local auth mode requires local users to be configured!')

        for user in pptp['local_users']:
            username = user['name']
            if not user['password']:
                raise ConfigError(f'Password required for local user "{username}"')

    elif pptp['auth_mode'] == 'radius':
        if len(pptp['radius_server']) == 0:
            raise ConfigError('RADIUS authentication requires at least one server')

        for radius in pptp['radius_server']:
            if not radius['key']:
                server = radius['server']
                raise ConfigError(f'Missing RADIUS secret key for server "{{ server }}"')

    if len(pptp['dnsv4']) > 2:
        raise ConfigError('Not more then two IPv4 DNS name-servers can be configured')


def generate(pptp):
    if not pptp:
        return None

    dirname = os.path.dirname(pptp_conf)
    if not os.path.exists(dirname):
        os.mkdir(dirname)

    render(pptp_conf, 'accel-ppp/pptp.config.tmpl', pptp, trim_blocks=True)

    if pptp['local_users']:
        render(pptp_chap_secrets, 'accel-ppp/chap-secrets.tmpl', pptp, trim_blocks=True)
        os.chmod(pptp_chap_secrets, S_IRUSR | S_IWUSR | S_IRGRP)
    else:
        if os.path.exists(pptp_chap_secrets):
             os.unlink(pptp_chap_secrets)


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
