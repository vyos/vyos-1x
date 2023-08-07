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

from shutil import rmtree
from sys import exit

from vyos.config import Config
from vyos.config import config_dict_merge
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.permission import chmod_755
from vyos.utils.dict import dict_search
from vyos.utils.file import write_file
from vyos.utils.network import is_addr_assigned
from vyos.base import Warning
from vyos import ConfigError
from vyos import airbag

airbag.enable()

squid_config_file = '/etc/squid/squid.conf'
squidguard_config_file = '/etc/squidguard/squidGuard.conf'
squidguard_db_dir = '/opt/vyatta/etc/config/url-filtering/squidguard/db'
user_group = 'proxy'


def check_blacklist_categorydb(config_section):
    if 'block_category' in config_section:
        for category in config_section['block_category']:
            check_categorydb(category)
    if 'allow_category' in config_section:
        for category in config_section['allow_category']:
            check_categorydb(category)


def check_categorydb(category: str):
    """
    Check if category's db exist
    :param category:
    :type str:
    """
    path_to_cat: str = f'{squidguard_db_dir}/{category}'
    if not os.path.exists(f'{path_to_cat}/domains.db') \
            and not os.path.exists(f'{path_to_cat}/urls.db') \
            and not os.path.exists(f'{path_to_cat}/expressions.db'):
        Warning(f'DB of category {category} does not exist.\n '
                f'Use [update webproxy blacklists] '
                f'or delete undefined category!')


def generate_sg_rule_localdb(category, list_type, role, proxy):
    if not category or not list_type or not role:
        return None

    cat_ = category.replace('-', '_')

    if role == 'default':
        path_to_cat = f'{cat_}'
    else:
        path_to_cat = f'rule.{role}.{cat_}'
    if isinstance(
            dict_search(f'url_filtering.squidguard.{path_to_cat}', proxy),
            list):
        # local block databases must be generated "on-the-fly"
        tmp = {
            'squidguard_db_dir': squidguard_db_dir,
            'category': f'{category}-{role}',
            'list_type': list_type,
            'rule': role
        }
        sg_tmp_file = '/tmp/sg.conf'
        db_file = f'{category}-{role}/{list_type}'
        domains = '\n'.join(
            dict_search(f'url_filtering.squidguard.{path_to_cat}', proxy))
        # local file
        write_file(f'{squidguard_db_dir}/{category}-{role}/local', '',
                   user=user_group, group=user_group)
        # database input file
        write_file(f'{squidguard_db_dir}/{db_file}', domains,
                   user=user_group, group=user_group)

        # temporary config file, deleted after generation
        render(sg_tmp_file, 'squid/sg_acl.conf.j2', tmp,
               user=user_group, group=user_group)

        call(
            f'su - {user_group} -c "squidGuard -d -c {sg_tmp_file} -C {db_file}"')

        if os.path.exists(sg_tmp_file):
            os.unlink(sg_tmp_file)
    else:
        # if category is not part of our configuration, clean out the
        # squidguard lists
        tmp = f'{squidguard_db_dir}/{category}-{role}'
        if os.path.exists(tmp):
            rmtree(f'{squidguard_db_dir}/{category}-{role}')


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'webproxy']
    if not conf.exists(base):
        return None

    proxy = conf.get_config_dict(base, key_mangling=('-', '_'),
                                 get_first_key=True)
    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = conf.get_config_defaults(**proxy.kwargs,
                                              recursive=True)

    # if no authentication method is supplied, no need to add defaults
    if not dict_search('authentication.method', proxy):
        default_values.pop('authentication')
    # if no url_filteringurl-filtering method is supplied, no need to add defaults
    if 'url_filtering' not in proxy:
        default_values.pop('url_filtering')
    else:
        # store path to squidGuard config, used when generating Squid config
        proxy['squidguard_conf'] = squidguard_config_file
        proxy['squidguard_db_dir'] = squidguard_db_dir

    proxy = config_dict_merge(default_values, proxy)

    return proxy


def verify(proxy):
    if not proxy:
        return None

    if 'listen_address' not in proxy:
        raise ConfigError('listen-address needs to be configured!')

    ldap_auth = dict_search('authentication.method', proxy) == 'ldap'

    for address, config in proxy['listen_address'].items():
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

    render(squid_config_file, 'squid/squid.conf.j2', proxy)
    render(squidguard_config_file, 'squid/squidGuard.conf.j2', proxy)

    cat_dict = {
        'local-block': 'domains',
        'local-block-keyword': 'expressions',
        'local-block-url': 'urls',
        'local-ok': 'domains',
        'local-ok-url': 'urls'
    }
    if dict_search(f'url_filtering.squidguard', proxy) is not None:
        squidgard_config_section = proxy['url_filtering']['squidguard']

        for category, list_type in cat_dict.items():
            generate_sg_rule_localdb(category, list_type, 'default', proxy)
        check_blacklist_categorydb(squidgard_config_section)

        if 'rule' in squidgard_config_section:
            for rule in squidgard_config_section['rule']:
                rule_config_section = squidgard_config_section['rule'][
                    rule]
                for category, list_type in cat_dict.items():
                    generate_sg_rule_localdb(category, list_type, rule, proxy)
                check_blacklist_categorydb(rule_config_section)

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

    if os.path.exists(squidguard_db_dir):
        chmod_755(squidguard_db_dir)
    call('systemctl reload-or-restart squid.service')
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
