#!/usr/bin/env python3
#
# Copyright (C) 2019-2020 VyOS maintainers and contributors
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
from socket import AF_INET, SOCK_STREAM, socket
from stat import S_IRUSR, S_IWUSR, S_IRGRP
from sys import exit
from time import sleep

from jinja2 import FileSystemLoader, Environment

from vyos.config import Config
from vyos.defaults import directories as vyos_data_dir
from vyos.util import run
from vyos.validate import is_ipv4
from vyos import ConfigError

pidfile = '/var/run/accel_l2tp.pid'
l2tp_conf = '/etc/accel-ppp/l2tp/l2tp.config'
l2tp_chap_secrets = '/etc/accel-ppp/l2tp/chap-secrets'

default_config_data = {
    'auth_mode': 'local',
    'auth_ppp_mppe': 'prefer',
    'auth_proto': ['auth_mschap_v2'],
    'chap_secrets_file': l2tp_chap_secrets,
    'client_ip_pool': None,
    'client_ip_subnets': [],
    'client_ipv6_pool': {},
    'dnsv4': [],
    'dnsv6': [],
    'gateway_address': '10.255.255.0',
    'local_users' : [],
    'mtu': '1436',
    'outside_addr': '',
    'ppp_mppe': 'prefer',
    'ppp_echo_failure' : '3',
    'ppp_echo_interval' : '30',
    'ppp_echo_timeout': '0',
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
    'wins': [],
    'ip6_column': '',
    'ip6_dp_column': '',
    'ppp_options': {},
    'thread_cnt': 1
}

def chk_con():
    """
    Depending on hardware and threads, daemon needs a little to start if it
    takes longer than 100 * 0.5 secs, exception is being raised not sure if
    that's the best way to check it, but it worked so far quite well
    """
    cnt = 0
    s = socket(AF_INET, SOCK_STREAM)
    while True:
        try:
            s.connect(("127.0.0.1", 2004))
            break
        except ConnectionRefusedError:
            sleep(0.5)
            cnt += 1
            if cnt == 100:
                raise("failed to start l2tp server")
                break


def _accel_cmd(command):
  return run(f'/usr/bin/accel-cmd -p 2004 {command}')


def get_config():
    conf = Config()
    base_path = ['vpn', 'l2tp', 'remote-access']
    if not conf.exists(base_path):
        return None

    conf.set_level(base_path)
    l2tp = deepcopy(default_config_data)

    cpu = os.cpu_count()
    if cpu > 1:
        l2tp['thread_cnt'] = int(cpu/2)

    ### general options ###
    if conf.exists(['name-server']):
        for name_server in conf.return_values(['name-server']):
            if is_ipv4(name_server):
                l2tp['dnsv4'].append(name_server)
            else:
                l2tp['dnsv6'].append(name_server)

    if conf.exists(['wins-server']):
        l2tp['wins'] = conf.return_values(['wins-server'])

    if conf.exists('outside-address'):
        l2tp['outside_addr'] = conf.return_value('outside-address')

    if conf.exists(['authentication', 'mode']):
        l2tp['auth_mode'] = conf.return_value(['authentication', 'mode'])

    if conf.exists(['authentication', 'protocols']):
        auth_mods = {
            'pap': 'auth_pap',
            'chap': 'auth_chap_md5',
            'mschap': 'auth_mschap_v1',
            'mschap-v2': 'auth_mschap_v2'
        }

        for proto in conf.return_values(['authentication', 'protocols']):
            l2tp['auth_proto'].append(auth_mods[proto])

    if conf.exists(['authentication', 'mppe']):
        l2tp['auth_ppp_mppe'] = conf.return_value(['authentication', 'mppe'])

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

            l2tp['local_users'].append(user)

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

            if conf.exists(['key']):
                radius['key'] = conf.return_value(['key'])

            if not conf.exists(['disable']):
                l2tp['radius_server'].append(radius)

        #
        # advanced radius-setting
        conf.set_level(base_path + ['authentication', 'radius'])

        if conf.exists(['acct-timeout']):
            l2tp['radius_acct_tmo'] = conf.return_value(['acct-timeout'])

        if conf.exists(['max-try']):
            l2tp['radius_max_try'] = conf.return_value(['max-try'])

        if conf.exists(['timeout']):
            l2tp['radius_timeout'] = conf.return_value(['timeout'])

        if conf.exists(['nas-identifier']):
            l2tp['radius_nas_id'] = conf.return_value(['nas-identifier'])

        if conf.exists(['nas-ip-address']):
            l2tp['radius_nas_ip'] = conf.return_value(['nas-ip-address'])

        if conf.exists(['source-address']):
            l2tp['radius_source_address'] = conf.return_value(['source-address'])

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

            l2tp['radius_dynamic_author'] = dae

        if conf.exists(['rate-limit', 'enable']):
            l2tp['radius_shaper_attr'] = 'Filter-Id'
            c_attr = ['rate-limit', 'enable', 'attribute']
            if conf.exists(c_attr):
                l2tp['radius_shaper_attr'] = conf.return_value(c_attr)

            c_vendor = ['rate-limit', 'enable', 'vendor']
            if conf.exists(c_vendor):
                l2tp['radius_shaper_vendor'] = conf.return_value(c_vendor)

    conf.set_level(base_path)
    if conf.exists(['client-ip-pool']):
        if conf.exists(['client-ip-pool', 'start']) and conf.exists(['client-ip-pool', 'stop']):
            start = conf.return_value(['client-ip-pool', 'start'])
            stop  = conf.return_value(['client-ip-pool', 'stop'])
            l2tp['client_ip_pool'] = start + '-' + re.search('[0-9]+$', stop).group(0)

    if conf.exists(['client-ip-pool', 'subnet']):
        l2tp['client_ip_subnets'] = conf.return_values(['client-ip-pool', 'subnet'])

    if conf.exists(['client-ipv6-pool', 'prefix']):
        l2tp['client_ipv6_pool']['prefix'] = conf.return_values(
            'client-ipv6-pool prefix')
        l2tp['ip6_column'] = 'ip6,'

    if conf.exists('client-ipv6-pool delegate-prefix'):
        l2tp['client_ipv6_pool']['delegate_prefix'] = conf.return_values(
            'client-ipv6-pool delegate-prefix')
        l2tp['ip6_dp_column'] = 'ip6-dp,'

    if conf.exists('mtu'):
        l2tp['mtu'] = conf.return_value('mtu')

    # gateway address
    if conf.exists('gateway-address'):
        l2tp['gateway_address'] = conf.return_value('gateway-address')
    else:
        # calculate gw-ip-address
        if conf.exists('client-ip-pool start'):
            # use start ip as gw-ip-address
            l2tp['gateway_address'] = conf.return_value(
                'client-ip-pool start')
        elif conf.exists('client-ip-pool subnet'):
            # use first ip address from first defined pool
            lst_ip = re.findall("\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", conf.return_values(
                'client-ip-pool subnet')[0])
            l2tp['gateway_address'] = lst_ip[0]

    # LNS secret
    if conf.exists(['lns', 'shared-secret']):
        l2tp['lns_shared_secret'] = conf.return_value(['lns', 'shared-secret'])

    if conf.exists(['ccp-disable']):
        l2tp[['ccp_disable']] = True

    # PPP options
    if conf.exists(['idle']):
        l2tp['ppp_echo_timeout'] = conf.return_value(['idle'])

    if conf.exists(['ppp-options', 'lcp-echo-failure']):
        l2tp['ppp_echo_failure'] = conf.return_value(['ppp-options', 'lcp-echo-failure'])

    if conf.exists(['ppp-options', 'lcp-echo-interval']):
        l2tp['ppp_echo_interval'] = conf.return_value(['ppp-options', 'lcp-echo-interval'])

    return l2tp


def verify(l2tp):
    if not l2tp:
        return None

    if l2tp['auth_mode'] == 'local':
        if not l2tp['local_users']:
            raise ConfigError('L2TP local auth mode requires local users to be configured!')

        for user in l2tp['local_users']:
            if not user['password']:
                raise ConfigError(f"Password required for user {user['name']}")

    elif l2tp['auth_mode'] == 'radius':
        if len(l2tp['radius_server']) == 0:
            raise ConfigError("RADIUS authentication requires at least one server")

        for radius in l2tp['radius_server']:
            if not radius['key']:
                raise ConfigError(f"Missing RADIUS secret for server {{ radius['key'] }}")

    # check for the existence of a client ip pool
    if not (l2tp['client_ip_pool'] or l2tp['client_ip_subnets']):
        raise ConfigError(
            "set vpn l2tp remote-access client-ip-pool requires subnet or start/stop IP pool")

    # check ipv6
    if 'delegate_prefix' in l2tp['client_ipv6_pool'] and not 'prefix' in l2tp['client_ipv6_pool']:
        raise ConfigError(
            "\"set vpn l2tp remote-access client-ipv6-pool prefix\" required for delegate-prefix ")

    if len(l2tp['wins']) > 2:
        raise ConfigError('Not more then two IPv4 WINS name-servers can be configured')

    if len(l2tp['dnsv4']) > 2:
        raise ConfigError('Not more then two IPv4 DNS name-servers can be configured')

    if len(l2tp['dnsv6']) > 3:
        raise ConfigError('Not more then three IPv6 DNS name-servers can be configured')

    return None


def generate(l2tp):
    if not l2tp:
        return None

    # Create configuration directory if it's non existent
    dirname = os.path.dirname(l2tp_conf)
    if not os.path.isdir(dirname):
        os.mkdir(dirname)

    # Prepare Jinja2 template loader from files
    tmpl_path = os.path.join(vyos_data_dir['data'], 'templates', 'l2tp')
    fs_loader = FileSystemLoader(tmpl_path)
    env = Environment(loader=fs_loader, trim_blocks=True)

    tmpl = env.get_template('l2tp.config.tmpl')
    config_text = tmpl.render(c)
    with open(l2tp_conf, 'w') as f:
        f.write(config_text)

    if l2tp['auth_mode'] == 'local':
        tmpl = env.get_template('chap-secrets.tmpl')
        config_text = tmpl.render(l2tp)
        with open(l2tp['chap_secrets_file'], 'w') as f:
            f.write(config_text)

        os.chmod(l2tp['chap_secrets_file'], S_IRUSR | S_IWUSR | S_IRGRP)

    else:
        if os.path.exists(l2tp['chap_secrets_file']):
             os.unlink(l2tp['chap_secrets_file'])

    return None


def apply(l2tp):
    if not l2tp:
        if os.path.exists(pidfile):
            _accel_cmd('shutdown hard')
            if os.path.exists(pidfile):
                os.remove(pidfile)
        return None

    if not os.path.exists(pidfile):
        ret = run(f'/usr/sbin/accel-pppd -c {l2tp_conf} -p {pidfile} -d')
        chk_con()
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
