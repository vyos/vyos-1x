#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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
from vyos.template import render
from vyos.util import call
from vyos.util import dict_search
from vyos.validate import is_addr_assigned
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

squid_config_file = '/etc/squid/squid.conf'
squidguard_config_file = '/etc/squidguard/squidGuard.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'webproxy']
    if not conf.exists(base):
        return None

    proxy = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)

    # if no authentication method is supplied, no need to add defaults
    if not dict_search('authentication.method', proxy):
        default_values.pop('authentication')
    # if no url_filteringurl-filtering method is supplied, no need to add defaults
    if 'url_filtering' not in proxy:
        default_values.pop('url_filtering')
    else:
        # store path to squidGuard config, used when generating Squid config
        proxy['squidguard_conf'] = squidguard_config_file

    # XXX: T2665: blend in proper cache-peer default values later
    default_values.pop('cache_peer')
    proxy = dict_merge(default_values, proxy)

    # XXX: T2665: blend in proper cache-peer default values
    if 'cache_peer' in proxy:
        default_values = defaults(base + ['cache-peer'])
        for peer in proxy['cache_peer']:
            proxy['cache_peer'][peer] = dict_merge(default_values,
                proxy['cache_peer'][peer])

    import pprint
    pprint.pprint(proxy)
    return proxy

def verify(proxy):
    if not proxy:
        return None

    if 'listen_address' not in proxy:
        raise ConfigError('listen-address needs to be configured!')

    ldap_auth = dict_search('authentication.method', proxy) == 'ldap'

    for address, config in proxy['listen_address'].items():
        if not is_addr_assigned(address):
            raise ConfigError(
                f'listen-address "{address}" not assigned on any interface!')
        if ldap_auth and 'disable_transparent' not in config:
            raise ConfigError('Authentication can not be configured when ' \
                              'proxy is in transparent mode')

    if 'outgoing_address' in proxy:
        address = proxy['outgoing_address']
        if not is_addr_assigned(address):
            raise ConfigError(
                f'outgoing-address "{address}" not assigned on any interface!')

    if 'authentication' in proxy:
        if 'method' not in proxy['authentication']:
            raise ConfigError('proxy authentication method required!')

        if ldap_auth:
            ldap_config = proxy['authentication']['ldap']

            if 'server' not in ldap_config:
                raise ConfigError(
                    'LDAP authentication enabled, but no server set')

            if 'password' in ldap_config and 'bind_dn' not in ldap_config:
                raise ConfigError(
                    'LDAP password can not be set when base-dn is undefined!')

            if 'bind_dn' in ldap_config and 'password' not in ldap_config:
                raise ConfigError(
                    'LDAP bind DN can not be set without password!')

            if 'base_dn' not in ldap_config:
                raise ConfigError('LDAP base-dn must be set!')

    if 'cache_peer' in proxy:
        for peer, config in proxy['cache_peer'].items():
            if 'address' not in config:
                raise ConfigError(f'Cache-peer "{peer}" address must be set!')

def generate(proxy):
    if not proxy:
        return None

    render(squid_config_file, 'squid/squid.conf.tmpl', proxy)
    render(squidguard_config_file, 'squid/squidGuard.conf.tmpl', proxy)

    return None

def apply(proxy):
    if not proxy:
        # proxy is removed in the commit
        call('systemctl stop squid.service')

        if os.path.exists(squid_config_file):
            os.unlink(squid_config_file)
        if os.path.exists(squidguard_config_file):
            os.unlink(squidguard_config_file)

        return None

    call('systemctl restart squid.service')
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
