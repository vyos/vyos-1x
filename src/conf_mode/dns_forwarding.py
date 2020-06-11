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
from copy import deepcopy

from vyos.config import Config
from vyos.hostsd_client import Client as hostsd_client
from vyos import ConfigError
from vyos.util import call, chown
from vyos.template import render

from vyos import airbag
airbag.enable()

pdns_rec_user = pdns_rec_group = 'pdns'
pdns_rec_run_dir = '/run/powerdns'
pdns_rec_lua_conf_file = f'{pdns_rec_run_dir}/recursor.conf.lua'
pdns_rec_hostsd_lua_conf_file = f'{pdns_rec_run_dir}/recursor.vyos-hostsd.conf.lua'
pdns_rec_hostsd_zones_file = f'{pdns_rec_run_dir}/recursor.forward-zones.conf'
pdns_rec_config_file = f'{pdns_rec_run_dir}/recursor.conf'

default_config_data = {
    'allow_from': [],
    'cache_size': 10000,
    'export_hosts_file': 'yes',
    'listen_address': [],
    'name_servers': [],
    'negative_ttl': 3600,
    'system': False,
    'domains': {},
    'dnssec': 'process-no-validate',
    'dhcp_interfaces': []
}

hostsd_tag = 'static'

def get_config(conf):
    dns = deepcopy(default_config_data)
    base = ['service', 'dns', 'forwarding']

    if not conf.exists(base):
        return None

    conf.set_level(base)

    if conf.exists(['allow-from']):
        dns['allow_from'] = conf.return_values(['allow-from'])

    if conf.exists(['cache-size']):
        cache_size = conf.return_value(['cache-size'])
        dns['cache_size'] = cache_size

    if conf.exists('negative-ttl'):
        negative_ttl = conf.return_value(['negative-ttl'])
        dns['negative_ttl'] = negative_ttl

    if conf.exists(['domain']):
        for domain in conf.list_nodes(['domain']):
            conf.set_level(base + ['domain', domain])
            entry = {
                'nslist': bracketize_ipv6_addrs(conf.return_values(['server'])),
                'addNTA': conf.exists(['addnta']),
                'recursion-desired': conf.exists(['recursion-desired'])
            }
            dns['domains'][domain] = entry

        conf.set_level(base)

    if conf.exists(['ignore-hosts-file']):
        dns['export_hosts_file'] = "no"

    if conf.exists(['name-server']):
        dns['name_servers'] = bracketize_ipv6_addrs(
                conf.return_values(['name-server']))

    if conf.exists(['system']):
        dns['system'] = True

    if conf.exists(['listen-address']):
        dns['listen_address'] = conf.return_values(['listen-address'])

    if conf.exists(['dnssec']):
        dns['dnssec'] = conf.return_value(['dnssec'])

    if conf.exists(['dhcp']):
        dns['dhcp_interfaces'] = conf.return_values(['dhcp'])

    return dns

def bracketize_ipv6_addrs(addrs):
    """Wraps each IPv6 addr in addrs in [], leaving IPv4 addrs untouched."""
    return ['[{0}]'.format(a) if a.count(':') > 1 else a for a in addrs]

def verify(conf, dns):
    # bail out early - looks like removal from running config
    if dns is None:
        return None

    if not dns['listen_address']:
        raise ConfigError(
            "Error: DNS forwarding requires a listen-address")

    if not dns['allow_from']:
        raise ConfigError(
                "Error: DNS forwarding requires an allow-from network")

    if dns['domains']:
        for domain in dns['domains']:
            if not dns['domains'][domain]['nslist']:
                raise ConfigError((
                    f'Error: No server configured for domain {domain}'))

    no_system_nameservers = False
    if dns['system'] and not (
            conf.exists(['system', 'name-server']) or
            conf.exists(['system', 'name-servers-dhcp']) ):
        no_system_nameservers = True
        print(("DNS forwarding warning: No 'system name-server' or "
                "'system name-servers-dhcp' set\n"))

    if (no_system_nameservers or not dns['system']) and not (
            dns['name_servers'] or dns['dhcp_interfaces']):
        print(("DNS forwarding warning: No 'dhcp', 'name-server' or 'system' "
            "nameservers set. Forwarding will operate as a recursor.\n"))

    return None

def generate(dns):
    # bail out early - looks like removal from running config
    if dns is None:
        return None

    render(pdns_rec_config_file, 'dns-forwarding/recursor.conf.tmpl',
            dns, user=pdns_rec_user, group=pdns_rec_group)

    render(pdns_rec_lua_conf_file, 'dns-forwarding/recursor.conf.lua.tmpl',
            dns, user=pdns_rec_user, group=pdns_rec_group)

    # if vyos-hostsd didn't create its files yet, create them (empty)
    for f in [pdns_rec_hostsd_lua_conf_file, pdns_rec_hostsd_zones_file]:
        with open(f, 'a'):
            pass
        chown(f, user=pdns_rec_user, group=pdns_rec_group)

    return None

def apply(dns):
    if dns is None:
        # DNS forwarding is removed in the commit
        call("systemctl stop pdns-recursor.service")
        if os.path.isfile(pdns_rec_config_file):
            os.unlink(pdns_rec_config_file)
    else:
        ### first apply vyos-hostsd config
        hc = hostsd_client()

        # add static nameservers to hostsd so they can be joined with other
        # sources
        hc.delete_name_servers([hostsd_tag])
        if dns['name_servers']:
            hc.add_name_servers({hostsd_tag: dns['name_servers']})

        # delete all nameserver tags
        hc.delete_name_server_tags_recursor(hc.get_name_server_tags_recursor())

        ## add nameserver tags - the order determines the nameserver order!
        # our own tag (static)
        hc.add_name_server_tags_recursor([hostsd_tag])

        if dns['system']:
            hc.add_name_server_tags_recursor(['system'])
        else:
            hc.delete_name_server_tags_recursor(['system'])

        # add dhcp nameserver tags for configured interfaces
        for intf in dns['dhcp_interfaces']:
            hc.add_name_server_tags_recursor(['dhcp-' + intf, 'dhcpv6-' + intf ])

        # hostsd will generate the forward-zones file
        # the list and keys() are required as get returns a dict, not list
        hc.delete_forward_zones(list(hc.get_forward_zones().keys()))
        if dns['domains']:
            hc.add_forward_zones(dns['domains'])

        # call hostsd to generate forward-zones and its lua-config-file
        hc.apply()

        ### finally (re)start pdns-recursor
        call("systemctl restart pdns-recursor.service")

if __name__ == '__main__':
    try:
        conf = Config()
        c = get_config(conf)
        verify(conf, c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
