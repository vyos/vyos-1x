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
from socket import socket, AF_INET, SOCK_STREAM
from copy import deepcopy
from stat import S_IRUSR, S_IWUSR, S_IRGRP
from jinja2 import FileSystemLoader, Environment

from vyos.config import Config
from vyos import ConfigError
from vyos.defaults import directories as vyos_data_dir
from vyos.util import process_running
from vyos.util import process_running, cmd, run

pidfile = r'/var/run/accel_sstp.pid'
sstp_cnf_dir = r'/etc/accel-ppp/sstp'
chap_secrets = sstp_cnf_dir + '/chap-secrets'
sstp_conf = sstp_cnf_dir + '/sstp.config'

# config path creation
if not os.path.exists(sstp_cnf_dir):
    os.makedirs(sstp_cnf_dir)

def chk_con():
    cnt = 0
    s = socket(AF_INET, SOCK_STREAM)
    while True:
        try:
            s.connect(("127.0.0.1", 2005))
            s.close()
            break
        except ConnectionRefusedError:
            sleep(0.5)
            cnt += 1
            if cnt == 100:
                raise("failed to start sstp server")
                break


def _accel_cmd(command):
    return run(f'/usr/bin/accel-cmd -p 2005 {command}')

default_config_data = {
    'local_users' : [],
    'auth_mode' : 'local',
    'auth_proto' : ['auth_mschap_v2'],
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
    'client_ip_pool' : [],
    'dnsv4' : [],
    'mtu' : '',
    'ppp_mppe' : 'prefer',
    'ppp_echo_failure' : '',
    'ppp_echo_interval' : '',
    'ppp_echo_timeout' : '',
    'thread_cnt' : 1
}

def get_config():
    sstp = deepcopy(default_config_data)
    base_path = ['vpn', 'sstp']
    conf = Config()
    if not conf.exists(base_path):
        return None

    conf.set_level(base_path)

    cpu = os.cpu_count()
    if cpu > 1:
        sstp['thread_cnt'] = int(cpu/2)

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
    # read in client ip pool settings
    conf.set_level(base_path + ['network-settings', 'client-ip-settings'])
    if conf.exists(['subnet']):
        sstp['client_ip_pool'] = conf.return_values(['subnet'])

    if conf.exists(['gateway-address']):
        sstp['client_gateway'] = conf.return_value(['gateway-address'])

    #
    # read in network settings
    conf.set_level(base_path + ['network-settings'])
    if conf.exists(['name-server']):
        sstp['dnsv4'] = conf.return_values(['name-server'])

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
            if not user['password']:
                raise ConfigError(f"Password required for user {user['name']}")

            # if up/download is set, check that both have a value
            if user['upload'] and not user['download']:
                raise ConfigError(f"Download speed value required for user {user['name']}")

            if user['download'] and not user['upload']:
                raise ConfigError(f"Upload speed value required for user {user['name']}")

        if not sstp['client_ip_pool']:
            raise ConfigError("Client IP subnet required")

        if not sstp['client_gateway']:
            raise ConfigError("Client gateway IP address required")

    if len(sstp['dnsv4']) > 2:
        raise ConfigError('Not more then two IPv4 DNS name-servers can be configured')

    if not sstp['ssl_ca'] or not sstp['ssl_cert'] or not sstp['ssl_key']:
        raise ConfigError('One or more SSL certificates missing')

    if not os.path.exists(sstp['ssl_ca']):
        raise ConfigError(f"CA cert file {sstp['ssl_ca']} does not exist")

    if not os.path.exists(sstp['ssl_cert']):
        raise ConfigError(f"SSL cert file {sstp['ssl_cert']} does not exist")

    if not os.path.exists(sstp['ssl_key']):
        raise ConfigError(f"SSL key file {sstp['ssl_key']} does not exist")

    if sstp['auth_mode'] == 'radius':
        if len(sstp['radius_server']) == 0:
            raise ConfigError("RADIUS authentication requires at least one server")

        for radius in sstp['radius_server']:
            if not radius['key']:
                raise ConfigError(f"Missing RADIUS secret for server {{ radius['key'] }}")

def generate(sstp):
    if sstp is None:
        return None

    # Prepare Jinja2 template loader from files
    tmpl_path = os.path.join(vyos_data_dir['data'], 'templates', 'sstp')
    fs_loader = FileSystemLoader(tmpl_path)
    env = Environment(loader=fs_loader, trim_blocks=True)

    # accel-cmd reload doesn't work so any change results in a restart of the daemon
    tmpl = env.get_template('sstp.config.tmpl')
    config_text = tmpl.render(sstp)
    with open(sstp_conf, 'w') as f:
        f.write(config_text)

    if sstp['local_users']:
        tmpl = env.get_template('chap-secrets.tmpl')
        config_text = tmpl.render(sstp)
        with open(chap_secrets, 'w') as f:
            f.write(config_text)

        os.chmod(chap_secrets, S_IRUSR | S_IWUSR | S_IRGRP)
    else:
        if os.path.exists(chap_secrets):
             os.unlink(chap_secrets)

    return sstp

def apply(sstp):
    if sstp is None:
        if process_running(pidfile):
            command = 'start-stop-daemon'
            command += ' --stop '
            command += ' --quiet'
            command += ' --oknodo'
            command += ' --pidfile ' + pidfile
            cmd(command)

        if os.path.exists(pidfile):
            os.remove(pidfile)

        return None

    if not process_running(pidfile):
        if os.path.exists(pidfile):
            os.remove(pidfile)

        command = 'start-stop-daemon'
        command += ' --start '
        command += ' --quiet'
        command += ' --oknodo'
        command += ' --pidfile ' + pidfile
        command += ' --exec /usr/sbin/accel-pppd'
        # now pass arguments to accel-pppd binary
        command += ' --'
        command += ' -c ' + sstp_conf
        command += ' -p ' + pidfile
        command += ' -d'
        cmd(command)

        chk_con()

    else:
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
