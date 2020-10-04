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
from vyos.configdict import dict_merge
from vyos.validate import is_ipv4
from vyos.template import render
from vyos.util import call
from vyos.util import get_half_cpus
from vyos.util import vyos_dict_search
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

pppoe_conf = r'/run/accel-pppd/pppoe.conf'
pppoe_chap_secrets = r'/run/accel-pppd/pppoe.chap-secrets'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'pppoe-server']
    if not conf.exists(base):
        return None

    pppoe = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)

    # defaults include RADIUS server specifics per TAG node which need to be
    # added to individual RADIUS servers instead - so we can simply delete them
    if vyos_dict_search('authentication.radius.server', default_values):
        del default_values['authentication']['radius']['server']
    # defaults include static-ip address per TAG node which need to be added to
    # individual local users instead - so we can simply delete them
    if vyos_dict_search('authentication.local_users.username', default_values):
        del default_values['authentication']['local_users']['username']

    pppoe = dict_merge(default_values, pppoe)

    # set CPUs cores to process requests
    pppoe.update({'thread_count' : get_half_cpus()})
    # we need to store the path to the secrets file
    pppoe.update({'chap_secrets_file' : pppoe_chap_secrets})

    # We can only have two IPv4 and three IPv6 nameservers - also they are
    # configured in a different way in the configuration, this is why we split
    # the configuration
    if 'name_server' in pppoe:
        ns_v4 = []
        ns_v6 = []
        for ns in pppoe['name_server']:
            if is_ipv4(ns): ns_v4.append(ns)
            else: ns_v6.append(ns)

        pppoe.update({'name_server_ipv4' : ns_v4, 'name_server_ipv6' : ns_v6})
        del pppoe['name_server']

    # Add individual RADIUS server default values
    if vyos_dict_search('authentication.radius.server', pppoe):
        default_values = defaults(base + ['authentication', 'radius', 'server'])

        for server in vyos_dict_search('authentication.radius.server', pppoe):
            pppoe['authentication']['radius']['server'][server] = dict_merge(
                default_values, pppoe['authentication']['radius']['server'][server])

    # Add individual local-user default values
    if vyos_dict_search('authentication.local_users.username', pppoe):
        default_values = defaults(base + ['authentication', 'local_users', 'username'])

        for username in vyos_dict_search('authentication.local_users.username', pppoe):
            pppoe['authentication']['local_users']['username'][username] = dict_merge(
                default_values, pppoe['authentication']['local_users']['username'][username])

    return pppoe


def verify(pppoe):
    if not pppoe:
        return None

    # vertify auth settings
    if vyos_dict_search('authentication.mode', pppoe) == 'local':
        if not vyos_dict_search('authentication.local_users', pppoe):
            raise ConfigError('PPPoE local auth mode requires local users to be configured!')

        for user in vyos_dict_search('authentication.local_users.username', pppoe):
            user_config = pppoe['authentication']['local_users']['username'][user]

            if 'password' not in user_config:
                raise ConfigError(f'Password required for local user "{user}"')

            if 'rate_limit' in user_config:
                # if up/download is set, check that both have a value
                if not {'upload', 'download'} <= set(user_config['rate_limit']):
                    raise ConfigError(f'User "{user}" has rate-limit configured for only one ' \
                                      'direction but both upload and download must be given!')

    elif vyos_dict_search('authentication.mode', pppoe) == 'radius':
        if not vyos_dict_search('authentication.radius.server', pppoe):
            raise ConfigError('RADIUS authentication requires at least one server')

        for server in vyos_dict_search('authentication.radius.server', pppoe):
            radius_config = pppoe['authentication']['radius']['server'][server]
            if 'key' not in radius_config:
                raise ConfigError(f'Missing RADIUS secret key for server "{server}"')

    if 'wins_server' in pppoe and len(pppoe['wins_server']) > 2:
        raise ConfigError('Not more then two IPv4 WINS name-servers can be configured')

    if 'name_server_ipv4' in pppoe:
        if len(pppoe['name_server_ipv4']) > 2:
            raise ConfigError('Not more then two IPv4 DNS name-servers ' \
                              'can be configured')

    if 'name_server_ipv6' in pppoe:
        if len(pppoe['name_server_ipv6']) > 3:
            raise ConfigError('Not more then three IPv6 DNS name-servers ' \
                              'can be configured')

    if 'interface' not in pppoe:
        raise ConfigError('At least one listen interface must be defined!')

    if 'gateway_address' not in pppoe:
        raise ConfigError('PPPoE server requires gateway-address to be configured!')

    # local ippool and gateway settings config checks
    if not (vyos_dict_search('client_ip_pool.subnet', pppoe) or
           (vyos_dict_search('client_ip_pool.start', pppoe) and
            vyos_dict_search('client_ip_pool.stop', pppoe))):
        print('Warning: No PPPoE client pool defined')

    if vyos_dict_search('authentication.radius.dynamic_author.server', pppoe):
        if not vyos_dict_search('authentication.radius.dynamic_author.key', pppoe):
            raise ConfigError('DA/CoE server key required!')

    return None


def generate(pppoe):
    if not pppoe:
        return None

    render(pppoe_conf, 'accel-ppp/pppoe.config.tmpl', pppoe, trim_blocks=True)

    if vyos_dict_search('authentication.mode', pppoe) == 'local':
        render(pppoe_chap_secrets, 'accel-ppp/chap-secrets.config_dict.tmpl',
               pppoe, trim_blocks=True, permission=0o640)
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
