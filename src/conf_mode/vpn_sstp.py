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

from time import sleep
from sys import exit
from copy import deepcopy
from stat import S_IRUSR, S_IWUSR, S_IRGRP

from vyos.config import Config
from vyos.template import render
from vyos.util import call, run, get_half_cpus
from vyos.validate import is_ipv4
from vyos import ConfigError

from vyos import airbag
airbag.enable()

sstp_conf = '/run/accel-pppd/sstp.conf'
sstp_chap_secrets = '/run/accel-pppd/sstp.chap-secrets'

default_config_data = {
    'local_users' : [],
    'auth_mode' : 'local',
    'auth_proto' : ['auth_mschap_v2'],
    'chap_secrets_file': sstp_chap_secrets, # used in Jinja2 template
    'client_ip_pool' : [],
    'client_ipv6_pool': [],
    'client_ipv6_delegate_prefix': [],
    'client_gateway': '',
    'dnsv4' : [],
    'dnsv6' : [],
    'radius_server' : [],
    'radius_acct_tmo' : '3',
    'radius_max_try' : '3',
    'radius_timeout' : '3',
    'radius_nas_id' : '',
    'radius_nas_ip' : '',
    'radius_source_address' : '',
    'radius_shaper_attr' : '',
    'radius_shaper_vendor': '',
    'radius_dynamic_author' : '',
    'ssl_ca' : '',
    'ssl_cert' : '',
    'ssl_key' : '',
    'mtu' : '',
    'ppp_mppe' : 'prefer',
    'ppp_echo_failure' : '',
    'ppp_echo_interval' : '',
    'ppp_echo_timeout' : '',
    'thread_cnt' : get_half_cpus()
}

def get_config():
    sstp = deepcopy(default_config_data)
    base_path = ['vpn', 'sstp']
    conf = Config()
    if not conf.exists(base_path):
        return None

    conf.set_level(base_path)

    if conf.exists(['authentication', 'mode']):
        sstp['auth_mode'] = conf.return_value(['authentication', 'mode'])

    #
    # local auth
    if conf.exists(['authentication', 'local-users']):
        for username in conf.list_nodes(['authentication', 'local-users', 'username']):
            user = {
                'name' : username,
                'password' : '',
                'state' : 'enabled',
                'ip' : '*',
                'upload' : None,
                'download' : None
            }

            conf.set_level(base_path + ['authentication', 'local-users', 'username', username])

            if conf.exists(['password']):
                user['password'] = conf.return_value(['password'])

            if conf.exists(['disable']):
                user['state'] = 'disable'

            if conf.exists(['static-ip']):
                user['ip'] = conf.return_value(['static-ip'])

            if conf.exists(['rate-limit', 'download']):
                user['download'] = conf.return_value(['rate-limit', 'download'])

            if conf.exists(['rate-limit', 'upload']):
                user['upload'] = conf.return_value(['rate-limit', 'upload'])

            sstp['local_users'].append(user)

    #
    # RADIUS auth and settings
    conf.set_level(base_path + ['authentication', 'radius'])
    if conf.exists(['server']):
        for server in conf.list_nodes(['server']):
            radius = {
                'server' : server,
                'key' : '',
                'fail_time' : 0,
                'port' : '1812',
                'acct_port' : '1813'
            }

            conf.set_level(base_path + ['authentication', 'radius', 'server', server])

            if conf.exists(['fail-time']):
                radius['fail_time'] = conf.return_value(['fail-time'])

            if conf.exists(['port']):
                radius['port'] = conf.return_value(['port'])

            if conf.exists(['acct-port']):
                radius['acct_port'] = conf.return_value(['acct-port'])

            if conf.exists(['key']):
                radius['key'] = conf.return_value(['key'])

            if not conf.exists(['disable']):
                sstp['radius_server'].append(radius)

        #
        # advanced radius-setting
        conf.set_level(base_path + ['authentication', 'radius'])

        if conf.exists(['acct-timeout']):
            sstp['radius_acct_tmo'] = conf.return_value(['acct-timeout'])

        if conf.exists(['max-try']):
            sstp['radius_max_try'] = conf.return_value(['max-try'])

        if conf.exists(['timeout']):
            sstp['radius_timeout'] = conf.return_value(['timeout'])

        if conf.exists(['nas-identifier']):
            sstp['radius_nas_id'] = conf.return_value(['nas-identifier'])

        if conf.exists(['nas-ip-address']):
            sstp['radius_nas_ip'] = conf.return_value(['nas-ip-address'])

        if conf.exists(['source-address']):
            sstp['radius_source_address'] = conf.return_value(['source-address'])

        # Dynamic Authorization Extensions (DOA)/Change Of Authentication (COA)
        if conf.exists(['dynamic-author']):
            dae = {
                'port' : '',
                'server' : '',
                'key' : ''
            }

            if conf.exists(['dynamic-author', 'server']):
                dae['server'] = conf.return_value(['dynamic-author', 'server'])

            if conf.exists(['dynamic-author', 'port']):
                dae['port'] = conf.return_value(['dynamic-author', 'port'])

            if conf.exists(['dynamic-author', 'key']):
                dae['key'] = conf.return_value(['dynamic-author', 'key'])

            sstp['radius_dynamic_author'] = dae

        if conf.exists(['rate-limit', 'enable']):
            sstp['radius_shaper_attr'] = 'Filter-Id'
            c_attr = ['rate-limit', 'enable', 'attribute']
            if conf.exists(c_attr):
                sstp['radius_shaper_attr'] = conf.return_value(c_attr)

            c_vendor = ['rate-limit', 'enable', 'vendor']
            if conf.exists(c_vendor):
                sstp['radius_shaper_vendor'] = conf.return_value(c_vendor)

    #
    # authentication protocols
    conf.set_level(base_path + ['authentication'])
    if conf.exists(['protocols']):
        # clear default list content, now populate with actual CLI values
        sstp['auth_proto'] = []
        auth_mods = {
            'pap': 'auth_pap',
            'chap': 'auth_chap_md5',
            'mschap': 'auth_mschap_v1',
            'mschap-v2': 'auth_mschap_v2'
        }

        for proto in conf.return_values(['protocols']):
            sstp['auth_proto'].append(auth_mods[proto])

    #
    # read in SSL certs
    conf.set_level(base_path + ['ssl'])
    if conf.exists(['ca-cert-file']):
        sstp['ssl_ca'] = conf.return_value(['ca-cert-file'])

    if conf.exists(['cert-file']):
        sstp['ssl_cert'] = conf.return_value(['cert-file'])

    if conf.exists(['key-file']):
        sstp['ssl_key'] = conf.return_value(['key-file'])


    #
    # read in client IPv4 pool
    conf.set_level(base_path + ['network-settings', 'client-ip-settings'])
    if conf.exists(['subnet']):
        sstp['client_ip_pool'] = conf.return_values(['subnet'])

    if conf.exists(['gateway-address']):
        sstp['client_gateway'] = conf.return_value(['gateway-address'])

    #
    # read in client IPv6 pool
    conf.set_level(base_path + ['network-settings', 'client-ipv6-pool'])
    if conf.exists(['prefix']):
        for prefix in conf.list_nodes(['prefix']):
            tmp = {
                'prefix': prefix,
                'mask': '64'
            }

            if conf.exists(['prefix', prefix, 'mask']):
                tmp['mask'] = conf.return_value(['prefix', prefix, 'mask'])

            sstp['client_ipv6_pool'].append(tmp)

    if conf.exists(['delegate']):
        for prefix in conf.list_nodes(['delegate']):
            tmp = {
                'prefix': prefix,
                'mask': ''
            }

            if conf.exists(['delegate', prefix, 'delegation-prefix']):
                tmp['mask'] = conf.return_value(['delegate', prefix, 'delegation-prefix'])

            sstp['client_ipv6_delegate_prefix'].append(tmp)

    #
    # read in network settings
    conf.set_level(base_path + ['network-settings'])
    if conf.exists(['name-server']):
        for name_server in conf.return_values(['name-server']):
            if is_ipv4(name_server):
                sstp['dnsv4'].append(name_server)
            else:
                sstp['dnsv6'].append(name_server)

    if conf.exists(['mtu']):
        sstp['mtu'] = conf.return_value(['mtu'])

    #
    # read in PPP stuff
    conf.set_level(base_path + ['ppp-settings'])
    if conf.exists('mppe'):
        sstp['ppp_mppe'] = conf.return_value(['ppp-settings', 'mppe'])

    if conf.exists(['lcp-echo-failure']):
        sstp['ppp_echo_failure'] = conf.return_value(['lcp-echo-failure'])

    if conf.exists(['lcp-echo-interval']):
        sstp['ppp_echo_interval'] = conf.return_value(['lcp-echo-interval'])

    if conf.exists(['lcp-echo-timeout']):
        sstp['ppp_echo_timeout'] = conf.return_value(['lcp-echo-timeout'])

    return sstp


def verify(sstp):
    if sstp is None:
        return None

    # vertify auth settings
    if sstp['auth_mode'] == 'local':
        if not sstp['local_users']:
            raise ConfigError('SSTP local auth mode requires local users to be configured!')

        for user in sstp['local_users']:
            username = user['name']
            if not user['password']:
                raise ConfigError(f'Password required for local user "{username}"')

            # if up/download is set, check that both have a value
            if user['upload'] and not user['download']:
                raise ConfigError(f'Download speed value required for local user "{username}"')

            if user['download'] and not user['upload']:
                raise ConfigError(f'Upload speed value required for local user "{username}"')

        if not sstp['client_ip_pool']:
            raise ConfigError('Client IP subnet required')

        if not sstp['client_gateway']:
            raise ConfigError('Client gateway IP address required')

    if len(sstp['dnsv4']) > 2:
        raise ConfigError('Not more then two IPv4 DNS name-servers can be configured')

    # check ipv6
    if sstp['client_ipv6_delegate_prefix'] and not sstp['client_ipv6_pool']:
        raise ConfigError('IPv6 prefix delegation requires client-ipv6-pool prefix')

    for prefix in sstp['client_ipv6_delegate_prefix']:
        if not prefix['mask']:
            raise ConfigError('Delegation-prefix required for individual delegated networks')

    if not sstp['ssl_ca'] or not sstp['ssl_cert'] or not sstp['ssl_key']:
        raise ConfigError('One or more SSL certificates missing')

    if not os.path.exists(sstp['ssl_ca']):
        file = sstp['ssl_ca']
        raise ConfigError(f'SSL CA certificate file "{file}" does not exist')

    if not os.path.exists(sstp['ssl_cert']):
        file = sstp['ssl_cert']
        raise ConfigError(f'SSL public key file "{file}" does not exist')

    if not os.path.exists(sstp['ssl_key']):
        file = sstp['ssl_key']
        raise ConfigError(f'SSL private key file "{file}" does not exist')

    if sstp['auth_mode'] == 'radius':
        if len(sstp['radius_server']) == 0:
            raise ConfigError('RADIUS authentication requires at least one server')

        for radius in sstp['radius_server']:
            if not radius['key']:
                server = radius['server']
                raise ConfigError(f'Missing RADIUS secret key for server "{ server }"')

def generate(sstp):
    if not sstp:
        return None

    # accel-cmd reload doesn't work so any change results in a restart of the daemon
    render(sstp_conf, 'accel-ppp/sstp.config.tmpl', sstp, trim_blocks=True)

    if sstp['local_users']:
        render(sstp_chap_secrets, 'accel-ppp/chap-secrets.tmpl', sstp, trim_blocks=True)
        os.chmod(sstp_chap_secrets, S_IRUSR | S_IWUSR | S_IRGRP)
    else:
        if os.path.exists(sstp_chap_secrets):
             os.unlink(sstp_chap_secrets)

    return sstp

def apply(sstp):
    if not sstp:
        call('systemctl stop accel-ppp@sstp.service')
        for file in [sstp_chap_secrets, sstp_conf]:
            if os.path.exists(file):
                os.unlink(file)

        return None

    call('systemctl restart accel-ppp@sstp.service')


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
