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
from sys import exit
from time import sleep

from jinja2 import FileSystemLoader, Environment

from vyos.config import Config
from vyos.defaults import directories as vyos_data_dir
from vyos.util import run
from vyos.validate import is_ipv4
from vyos import ConfigError

pidfile = r'/var/run/accel_l2tp.pid'
l2tp_cnf_dir = r'/etc/accel-ppp/l2tp'
chap_secrets = l2tp_cnf_dir + '/chap-secrets'
l2tp_conf = l2tp_cnf_dir + '/l2tp.config'


# config path creation
if not os.path.exists(l2tp_cnf_dir):
    os.makedirs(l2tp_cnf_dir)


default_config_data = {
    'authentication': {
        'radiussrv': {},
        'radiusopt': {},
        'mppe': 'prefer'
    },
    'auth_proto' : [],
    'local_users' : [],
    'auth_mode' : 'local',
    'radius_server' : [],
    'outside_addr': '',
    'gateway_address': '10.255.255.0',
    'dnsv4': [],
    'dnsv6': [],
    'wins': [],
    'client_ip_pool': None,
    'client_ip_subnets': [],
    'client_ipv6_pool': {},
    'mtu': '1436',
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

    conf.set_level(base_path)
    # authentication mode radius servers and settings
    if conf.exists('authentication mode radius'):
        rsrvs = conf.list_nodes('authentication radius server')
        for rsrv in rsrvs:
            if conf.return_value('authentication radius server ' + rsrv + ' fail-time') == None:
                ftime = '0'
            else:
                ftime = str(conf.return_value(
                    'authentication radius server ' + rsrv + ' fail-time'))
            if conf.return_value('authentication radius-server ' + rsrv + ' req-limit') == None:
                reql = '0'
            else:
                reql = str(conf.return_value(
                    'authentication radius server ' + rsrv + ' req-limit'))

            l2tp['authentication']['radiussrv'].update(
                {
                    rsrv: {
                        'secret': conf.return_value('authentication radius server ' + rsrv + ' key'),
                        'fail-time': ftime,
                        'req-limit': reql
                    }
                }
            )
        # Source ip address feature
        if conf.exists('authentication radius source-address'):
            l2tp['authentication']['radius_source_address'] = conf.return_value(
                'authentication radius source-address')

        # advanced radius-setting
        if conf.exists('authentication radius acct-timeout'):
            l2tp['authentication']['radiusopt']['acct-timeout'] = conf.return_value(
                'authentication radius acct-timeout')
        if conf.exists('authentication radius max-try'):
            l2tp['authentication']['radiusopt']['max-try'] = conf.return_value(
                'authentication radius max-try')
        if conf.exists('authentication radius timeout'):
            l2tp['authentication']['radiusopt']['timeout'] = conf.return_value(
                'authentication radius timeout')
        if conf.exists('authentication radius nas-identifier'):
            l2tp['authentication']['radiusopt']['nas-id'] = conf.return_value(
                'authentication radius nas-identifier')
        if conf.exists('authentication radius dae-server'):
            # Set default dae-server port if not defined
            if conf.exists('authentication radius dae-server port'):
                dae_server_port = conf.return_value(
                    'authentication radius dae-server port')
            else:
                dae_server_port = "3799"
            l2tp['authentication']['radiusopt'].update(
                {
                    'dae-srv': {
                        'ip-addr': conf.return_value('authentication radius dae-server ip-address'),
                        'port': dae_server_port,
                        'secret': str(conf.return_value('authentication radius dae-server secret'))
                    }
                }
            )
        # filter-id is the internal accel default if attribute is empty
        # set here as default for visibility which may change in the future
        if conf.exists('authentication radius rate-limit enable'):
            if not conf.exists('authentication radius rate-limit attribute'):
                l2tp['authentication']['radiusopt']['shaper'] = {
                    'attr': 'Filter-Id'
                }
            else:
                l2tp['authentication']['radiusopt']['shaper'] = {
                    'attr': conf.return_value('authentication radius rate-limit attribute')
                }
            if conf.exists('authentication radius rate-limit vendor'):
                l2tp['authentication']['radiusopt']['shaper']['vendor'] = conf.return_value(
                    'authentication radius rate-limit vendor')

    if conf.exists('client-ip-pool'):
        if conf.exists('client-ip-pool start') and conf.exists('client-ip-pool stop'):
            l2tp['client_ip_pool'] = conf.return_value(
                'client-ip-pool start') + '-' + re.search('[0-9]+$', conf.return_value('client-ip-pool stop')).group(0)

    if conf.exists('client-ip-pool subnet'):
        l2tp['client_ip_subnets'] = conf.return_values(
            'client-ip-pool subnet')

    if conf.exists('client-ipv6-pool prefix'):
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

    #
    # authentication protocols
    conf.set_level(base_path + ['authentication'])
    if conf.exists(['protocols']):
        auth_mods = {
            'pap': 'auth_pap',
            'chap': 'auth_chap_md5',
            'mschap': 'auth_mschap_v1',
            'mschap-v2': 'auth_mschap_v2'
        }

        for proto in conf.return_values(['protocols']):
            l2tp['auth_proto'].append(auth_mods[proto])

    else:
        l2tp['auth_proto'] = ['auth_mschap_v2']

    if conf.exists('authentication mppe'):
        l2tp['authentication']['mppe'] = conf.return_value(
            'authentication mppe')

    if conf.exists('idle'):
        l2tp['idle_timeout'] = conf.return_value('idle')

    # LNS secret
    if conf.exists('lns shared-secret'):
        l2tp['lns_shared_secret'] = conf.return_value('lns shared-secret')

    if conf.exists('ccp-disable'):
        l2tp['ccp_disable'] = True

    # ppp_options
    ppp_options = {}
    if conf.exists('ppp-options'):
        if conf.exists('ppp-options lcp-echo-failure'):
            ppp_options['lcp-echo-failure'] = conf.return_value(
                'ppp-options lcp-echo-failure')
        if conf.exists('ppp-options lcp-echo-interval'):
            ppp_options['lcp-echo-interval'] = conf.return_value(
                'ppp-options lcp-echo-interval')

    if len(ppp_options) != 0:
        l2tp['ppp_options'] = ppp_options

    import pprint
    pprint.pprint(l2tp)
    return l2tp


def verify(l2tp):
    if l2tp == None:
        return None

    if l2tp['auth_mode'] == 'local':
        if not l2tp['local_users']:
            raise ConfigError('L2TP local auth mode requires local users to be configured!')

        for user in l2tp['local_users']:
            if not user['password']:
                raise ConfigError(f"Password required for user {user['name']}")

    elif l2tp['auth_mode'] == 'radius':
        if len(l2tp['authentication']['radiussrv']) == 0:
            raise ConfigError('radius server required')

        for rsrv in l2tp['authentication']['radiussrv']:
            if l2tp['authentication']['radiussrv'][rsrv]['secret'] == None:
                raise ConfigError('radius server ' + rsrv +
                                  ' needs a secret configured')

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
    if l2tp == None:
        return None

    # Prepare Jinja2 template loader from files
    tmpl_path = os.path.join(vyos_data_dir['data'], 'templates', 'l2tp')
    fs_loader = FileSystemLoader(tmpl_path)
    env = Environment(loader=fs_loader, trim_blocks=True)

    tmpl = env.get_template('l2tp.config.tmpl')
    config_text = tmpl.render(c)
    open(l2tp_conf, 'w').write(config_text)

    if l2tp['auth_mode'] == 'local':
        tmpl = env.get_template('chap-secrets.tmpl')
        chap_secrets_txt = tmpl.render(l2tp)
        old_umask = os.umask(0o077)
        with open(chap_secrets, 'w') as f:
            f.write(chap_secrets_txt)
        os.umask(old_umask)

    return None


def apply(l2tp):
    if l2tp == None:
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
