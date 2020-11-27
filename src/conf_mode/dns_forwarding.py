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
from vyos.hostsd_client import Client as hostsd_client
from vyos.template import render
from vyos.template import is_ipv6
from vyos.util import call
from vyos.util import chown
from vyos.util import dict_search
from vyos.xml import defaults

from vyos import ConfigError
from vyos import airbag
airbag.enable()

pdns_rec_user = pdns_rec_group = 'pdns'
pdns_rec_run_dir = '/run/powerdns'
pdns_rec_lua_conf_file = f'{pdns_rec_run_dir}/recursor.conf.lua'
pdns_rec_hostsd_lua_conf_file = f'{pdns_rec_run_dir}/recursor.vyos-hostsd.conf.lua'
pdns_rec_hostsd_zones_file = f'{pdns_rec_run_dir}/recursor.forward-zones.conf'
pdns_rec_config_file = f'{pdns_rec_run_dir}/recursor.conf'

hostsd_tag = 'static'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'dns', 'forwarding']
    if not conf.exists(base):
        return None

    dns = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)
    dns = dict_merge(default_values, dns)

    # some additions to the default dictionary
    if 'system' in dns:
        base_nameservers = ['system', 'name-server']
        if conf.exists(base_nameservers):
            dns.update({'system_name_server': conf.return_values(base_nameservers)})

        base_nameservers_dhcp = ['system', 'name-servers-dhcp']
        if conf.exists(base_nameservers_dhcp):
            dns.update({'system_name_server_dhcp': conf.return_values(base_nameservers_dhcp)})

    # Split the source_address property into separate IPv4 and IPv6 lists
    # NOTE: In future versions of pdns-recursor (> 4.4.0), this logic can be removed
    # as both IPv4 and IPv6 addresses can be specified in a single setting.
    source_address_v4 = []
    source_address_v6 = []

    for source_address in dns['source_address']:
        if is_ipv6(source_address):
            source_address_v6.append(source_address)
        else:
            source_address_v4.append(source_address)

    dns.update({'source_address_v4': source_address_v4})
    dns.update({'source_address_v6': source_address_v6})

    return dns

def verify(dns):
    # bail out early - looks like removal from running config
    if not dns:
        return None

    if 'listen_address' not in dns:
        raise ConfigError('DNS forwarding requires a listen-address')

    if 'allow_from' not in dns:
        raise ConfigError('DNS forwarding requires an allow-from network')

    # we can not use dict_search() when testing for domain servers
    # as a domain will contains dot's which is out dictionary delimiter.
    if 'domain' in dns:
        for domain in dns['domain']:
            if 'server' not in dns['domain'][domain]:
                raise ConfigError(f'No server configured for domain {domain}!')

    if 'system' in dns:
        if not ('system_name_server' in dns or 'system_name_server_dhcp' in dns):
            print("Warning: No 'system name-server' or 'system " \
                  "name-servers-dhcp' configured")

    return None

def generate(dns):
    # bail out early - looks like removal from running config
    if not dns:
        return None

    render(pdns_rec_config_file, 'dns-forwarding/recursor.conf.tmpl',
            dns, user=pdns_rec_user, group=pdns_rec_group)

    render(pdns_rec_lua_conf_file, 'dns-forwarding/recursor.conf.lua.tmpl',
            dns, user=pdns_rec_user, group=pdns_rec_group)

    # if vyos-hostsd didn't create its files yet, create them (empty)
    for file in [pdns_rec_hostsd_lua_conf_file, pdns_rec_hostsd_zones_file]:
        with open(file, 'a'):
            pass
        chown(file, user=pdns_rec_user, group=pdns_rec_group)

    return None

def apply(dns):
    if not dns:
        # DNS forwarding is removed in the commit
        call('systemctl stop pdns-recursor.service')

        if os.path.isfile(pdns_rec_config_file):
            os.unlink(pdns_rec_config_file)
    else:
        ### first apply vyos-hostsd config
        hc = hostsd_client()

        # add static nameservers to hostsd so they can be joined with other
        # sources
        hc.delete_name_servers([hostsd_tag])
        if 'name_server' in dns:
            hc.add_name_servers({hostsd_tag: dns['name_server']})

        # delete all nameserver tags
        hc.delete_name_server_tags_recursor(hc.get_name_server_tags_recursor())

        ## add nameserver tags - the order determines the nameserver order!
        # our own tag (static)
        hc.add_name_server_tags_recursor([hostsd_tag])

        if 'system' in dns:
            hc.add_name_server_tags_recursor(['system'])
        else:
            hc.delete_name_server_tags_recursor(['system'])

        # add dhcp nameserver tags for configured interfaces
        if 'system_name_server_dhcp' in dns:
            for interface in dns['system_name_server_dhcp']:
                hc.add_name_server_tags_recursor(['dhcp-' + interface,
                                                  'dhcpv6-' + interface ])

        # hostsd will generate the forward-zones file
        # the list and keys() are required as get returns a dict, not list
        hc.delete_forward_zones(list(hc.get_forward_zones().keys()))
        if 'domain' in dns:
            hc.add_forward_zones(dns['domain'])

        # call hostsd to generate forward-zones and its lua-config-file
        hc.apply()

        ### finally (re)start pdns-recursor
        call('systemctl restart pdns-recursor.service')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
