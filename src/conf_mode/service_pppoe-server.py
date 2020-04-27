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
from vyos.validate import is_ipv4
from vyos import ConfigError

pppoe_conf = r'/run/accel-pppd/pppoe.conf'
pppoe_chap_secrets = r'/run/accel-pppd/pppoe.chap-secrets'

default_config_data = {
    'auth_mode': 'local',
    'auth_proto': ['auth_mschap_v2', 'auth_mschap_v1', 'auth_chap_md5', 'auth_pap'],
    'chap_secrets_file': pppoe_chap_secrets, # used in Jinja2 template
    'client_ip_pool': '',
    'client_ip_subnets': [],
    'client_ipv6_pool': [],
    'client_ipv6_delegate_prefix': [],
    'concentrator': 'vyos-ac',
    'interfaces': [],
    'local_users' : [],

    'svc_name': [],
    'dnsv4': [],
    'dnsv6': [],
    'wins': [],
    'mtu': '1492',

    'limits_burst': '',
    'limits_connections': '',
    'limits_timeout': '',

    'pado_delay': '',
    'ppp_ccp': False,
    'ppp_gw': '',
    'ppp_ipv4': '',
    'ppp_ipv6': '',
    'ppp_ipv6_accept_peer_intf_id': False,
    'ppp_ipv6_intf_id': '',
    'ppp_ipv6_peer_intf_id': '',
    'ppp_echo_failure': '3',
    'ppp_echo_interval': '30',
    'ppp_echo_timeout': '0',
    'ppp_min_mtu': '',
    'ppp_mppe': 'prefer',
    'ppp_mru': '',

    'radius_server': [],
    'radius_acct_tmo': '3',
    'radius_max_try': '3',
    'radius_timeout': '3',
    'radius_nas_id': '',
    'radius_nas_ip': '',
    'radius_source_address': '',
    'radius_shaper_attr': '',
    'radius_shaper_vendor': '',
    'radius_dynamic_author': '',
    'sesscrtl': 'replace',
    'snmp': False,
    'thread_cnt': get_half_cpus()
}

def get_config():
    conf = Config()
    base_path = ['service', 'pppoe-server']
    if not conf.exists(base_path):
        return None

    conf.set_level(base_path)
    pppoe = deepcopy(default_config_data)

    # general options
    if conf.exists(['access-concentrator']):
        pppoe['concentrator'] = conf.return_value(['access-concentrator'])

    if conf.exists(['service-name']):
        pppoe['svc_name'] = conf.return_values(['service-name'])

    if conf.exists(['interface']):
        for interface in conf.list_nodes(['interface']):
            conf.set_level(base_path + ['interface', interface])
            tmp = {
                'name': interface,
                'vlans': []
            }

            if conf.exists(['vlan-id']):
                tmp['vlans'] += conf.return_values(['vlan-id'])

            if conf.exists(['vlan-range']):
                tmp['vlans'] += conf.return_values(['vlan-range'])

            pppoe['interfaces'].append(tmp)

    conf.set_level(base_path)

    if conf.exists(['local-ip']):
        pppoe['ppp_gw'] = conf.return_value(['local-ip'])

    if conf.exists(['name-server']):
        for name_server in conf.return_values(['name-server']):
            if is_ipv4(name_server):
                pppoe['dnsv4'].append(name_server)
            else:
                pppoe['dnsv6'].append(name_server)

    if conf.exists(['wins-server']):
        pppoe['wins'] = conf.return_values(['wins-server'])


    if conf.exists(['client-ip-pool']):
        if conf.exists(['client-ip-pool', 'start']) and conf.exists(['client-ip-pool', 'stop']):
            start = conf.return_value(['client-ip-pool', 'start'])
            stop  = conf.return_value(['client-ip-pool', 'stop'])
            pppoe['client_ip_pool'] = start + '-' + re.search('[0-9]+$', stop).group(0)

        if conf.exists(['client-ip-pool', 'subnet']):
            pppoe['client_ip_subnets'] = conf.return_values(['client-ip-pool', 'subnet'])


    if conf.exists(['client-ipv6-pool', 'prefix']):
        for prefix in conf.list_nodes(['client-ipv6-pool', 'prefix']):
            tmp = {
                'prefix': prefix,
                'mask': '64'
            }

            if conf.exists(['client-ipv6-pool', 'prefix', prefix, 'mask']):
                tmp['mask'] = conf.return_value(['client-ipv6-pool', 'prefix', prefix, 'mask'])

            pppoe['client_ipv6_pool'].append(tmp)


    if conf.exists(['client-ipv6-pool', 'delegate']):
        for prefix in conf.list_nodes(['client-ipv6-pool', 'delegate']):
            tmp = {
                'prefix': prefix,
                'mask': ''
            }

            if conf.exists(['client-ipv6-pool', 'delegate', prefix, 'delegation-prefix']):
                tmp['mask'] = conf.return_value(['client-ipv6-pool', 'delegate', prefix, 'delegation-prefix'])

            pppoe['client_ipv6_delegate_prefix'].append(tmp)


    if conf.exists(['limits']):
        if conf.exists(['limits', 'burst']):
            pppoe['limits_burst'] = conf.return_value(['limits', 'burst'])

        if conf.exists(['limits', 'connection-limit']):
            pppoe['limits_connections'] = conf.return_value(['limits', 'connection-limit'])

        if conf.exists(['limits', 'timeout']):
            pppoe['limits_timeout'] = conf.return_value(['limits', 'timeout'])


    if conf.exists(['snmp']):
        pppoe['snmp'] = True

    if conf.exists(['snmp', 'master-agent']):
        pppoe['snmp'] = 'enable-ma'

    # authentication mode local
    if conf.exists(['authentication', 'mode']):
        pppoe['auth_mode'] = conf.return_value(['authentication', 'mode'])

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

            pppoe['local_users'].append(user)

    conf.set_level(base_path)

    if conf.exists(['authentication', 'protocols']):
        auth_mods = {
            'mschap-v2': 'auth_mschap_v2',
            'mschap': 'auth_mschap_v1',
            'chap': 'auth_chap_md5',
            'pap': 'auth_pap'
        }

        pppoe['auth_proto'] = []
        for proto in conf.return_values(['authentication', 'protocols']):
            pppoe['auth_proto'].append(auth_mods[proto])

    #
    # authentication mode radius servers and settings
    if conf.exists(['authentication', 'mode', 'radius']):

        for server in conf.list_nodes(['authentication', 'radius', 'server']):
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

            if conf.exists(['key']):
                radius['key'] = conf.return_value(['key'])

            if not conf.exists(['disable']):
                pppoe['radius_server'].append(radius)

        #
        # advanced radius-setting
        conf.set_level(base_path + ['authentication', 'radius'])

        if conf.exists(['acct-timeout']):
            pppoe['radius_acct_tmo'] = conf.return_value(['acct-timeout'])

        if conf.exists(['max-try']):
            pppoe['radius_max_try'] = conf.return_value(['max-try'])

        if conf.exists(['timeout']):
            pppoe['radius_timeout'] = conf.return_value(['timeout'])

        if conf.exists(['nas-identifier']):
            pppoe['radius_nas_id'] = conf.return_value(['nas-identifier'])

        if conf.exists(['nas-ip-address']):
            pppoe['radius_nas_ip'] = conf.return_value(['nas-ip-address'])

        if conf.exists(['source-address']):
            pppoe['radius_source_address'] = conf.return_value(['source-address'])

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

            pppoe['radius_dynamic_author'] = dae

        # RADIUS based rate-limiter
        if conf.exists(['rate-limit', 'enable']):
            pppoe['radius_shaper_attr'] = 'Filter-Id'
            c_attr = ['rate-limit', 'enable', 'attribute']
            if conf.exists(c_attr):
                pppoe['radius_shaper_attr'] = conf.return_value(c_attr)

            c_vendor = ['rate-limit', 'enable', 'vendor']
            if conf.exists(c_vendor):
                pppoe['radius_shaper_vendor'] = conf.return_value(c_vendor)

    # re-set config level
    conf.set_level(base_path)

    if conf.exists(['mtu']):
        pppoe['mtu'] = conf.return_value(['mtu'])

    if conf.exists(['session-control']):
        pppoe['session_control'] = conf.return_value(['session-control'])

    # ppp_options
    if conf.exists(['ppp-options']):
        conf.set_level(base_path + ['ppp-options'])

        if conf.exists(['ccp']):
            pppoe['ppp_ccp'] = True

        if conf.exists(['ipv4']):
            pppoe['ppp_ipv4'] = conf.return_value(['ipv4'])

        if conf.exists(['ipv6']):
            pppoe['ppp_ipv6'] = conf.return_value(['ipv6'])

        if conf.exists(['ipv6-accept-peer-intf-id']):
            pppoe['ppp_ipv6_peer_intf_id'] = True

        if conf.exists(['ipv6-intf-id']):
            pppoe['ppp_ipv6_intf_id'] = conf.return_value(['ipv6-intf-id'])

        if conf.exists(['ipv6-peer-intf-id']):
            pppoe['ppp_ipv6_peer_intf_id'] = conf.return_value(['ipv6-peer-intf-id'])

        if conf.exists(['lcp-echo-failure']):
            pppoe['ppp_echo_failure'] = conf.return_value(['lcp-echo-failure'])

        if conf.exists(['lcp-echo-failure']):
            pppoe['ppp_echo_interval'] = conf.return_value(['lcp-echo-failure'])

        if conf.exists(['lcp-echo-timeout']):
            pppoe['ppp_echo_timeout'] = conf.return_value(['lcp-echo-timeout'])

        if conf.exists(['min-mtu']):
            pppoe['ppp_min_mtu'] = conf.return_value(['min-mtu'])

        if conf.exists(['mppe']):
            pppoe['ppp_mppe'] = conf.return_value(['mppe'])

        if conf.exists(['mru']):
            pppoe['ppp_mru'] = conf.return_value(['mru'])

    if conf.exists(['pado-delay']):
        pppoe['pado_delay'] = '0'
        a = {}
        for id in conf.list_nodes(['pado-delay']):
            if not conf.return_value(['pado-delay', id, 'sessions']):
                a[id] = 0
            else:
                a[id] = conf.return_value(['pado-delay', id, 'sessions'])

        for k in sorted(a.keys()):
            if k != sorted(a.keys())[-1]:
                pppoe['pado_delay'] += ",{0}:{1}".format(k, a[k])
            else:
                pppoe['pado_delay'] += ",{0}:{1}".format('-1', a[k])

    return pppoe


def verify(pppoe):
    if not pppoe:
        return None

    # vertify auth settings
    if pppoe['auth_mode'] == 'local':
        if not pppoe['local_users']:
            raise ConfigError('PPPoE local auth mode requires local users to be configured!')

        for user in pppoe['local_users']:
            username = user['name']
            if not user['password']:
                raise ConfigError(f'Password required for local user "{username}"')

            # if up/download is set, check that both have a value
            if user['upload'] and not user['download']:
                raise ConfigError(f'Download speed value required for local user "{username}"')

            if user['download'] and not user['upload']:
                raise ConfigError(f'Upload speed value required for local user "{username}"')

    elif pppoe['auth_mode'] == 'radius':
        if len(pppoe['radius_server']) == 0:
            raise ConfigError('RADIUS authentication requires at least one server')

        for radius in pppoe['radius_server']:
            if not radius['key']:
                server = radius['server']
                raise ConfigError(f'Missing RADIUS secret key for server "{ server }"')

    if len(pppoe['wins']) > 2:
        raise ConfigError('Not more then two IPv4 WINS name-servers can be configured')

    if len(pppoe['dnsv4']) > 2:
        raise ConfigError('Not more then two IPv4 DNS name-servers can be configured')

    if len(pppoe['dnsv6']) > 3:
        raise ConfigError('Not more then three IPv6 DNS name-servers can be configured')

    # local ippool and gateway settings config checks
    if pppoe['client_ip_subnets'] or pppoe['client_ip_pool']:
        if not pppoe['ppp_gw']:
            raise ConfigError('PPPoE server requires local IP to be configured')

    if pppoe['ppp_gw'] and not pppoe['client_ip_subnets'] and not pppoe['client_ip_pool']:
        print("Warning: No PPPoE client pool defined")

    return None


def generate(pppoe):
    if not pppoe:
        return None

    render(pppoe_conf, 'accel-ppp/pppoe.config.tmpl', pppoe, trim_blocks=True)

    if pppoe['local_users']:
        render(pppoe_chap_secrets, 'accel-ppp/chap-secrets.tmpl', pppoe, trim_blocks=True)
        os.chmod(pppoe_chap_secrets, S_IRUSR | S_IWUSR | S_IRGRP)
    else:
        if os.path.exists(pppoe_chap_secrets):
             os.unlink(pppoe_chap_secrets)

    return None


def apply(pppoe):
    if not pppoe:
        call('systemctl stop accel-ppp@pppoe.service')
        for file in [pppoe_conf, pppoe_chap_secrets]:
            if os.path.exists(file):
                os.unlink(file)

        return None

    call('systemctl restart accel-ppp@pppoe.service')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
