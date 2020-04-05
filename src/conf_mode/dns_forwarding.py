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
import argparse

from sys import exit
from copy import deepcopy
from jinja2 import FileSystemLoader, Environment

from vyos.config import Config
from vyos.defaults import directories as vyos_data_dir
from vyos.hostsd_client import Client as hostsd_client
from vyos.util import wait_for_commit_lock
from vyos import ConfigError

parser = argparse.ArgumentParser()
parser.add_argument("--dhclient", action="store_true",
                    help="Started from dhclient-script")

config_file = r'/etc/powerdns/recursor.conf'

default_config_data = {
    'allow_from': [],
    'cache_size': 10000,
    'export_hosts_file': 'yes',
    'listen_on': [],
    'name_servers': [],
    'negative_ttl': 3600,
    'domains': [],
    'dnssec': 'process-no-validate'
}


def get_config(arguments):
    dns = deepcopy(default_config_data)
    conf = Config()
    base = ['service', 'dns', 'forwarding']

    if arguments.dhclient:
        conf.exists = conf.exists_effective
        conf.return_value = conf.return_effective_value
        conf.return_values = conf.return_effective_values

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
        for node in conf.list_nodes(['domain']):
            servers = conf.return_values(['domain', node, 'server'])
            domain = {
                "name": node,
                "servers": bracketize_ipv6_addrs(servers)
            }
            dns['domains'].append(domain)

    if conf.exists(['ignore-hosts-file']):
        dns['export_hosts_file'] = "no"

    if conf.exists(['name-server']):
        name_servers = conf.return_values(['name-server'])
        dns['name_servers'] = dns['name_servers'] + name_servers

    if conf.exists(['system']):
        conf.set_level(['system'])
        system_name_servers = []
        system_name_servers = conf.return_values(['name-server'])
        if not system_name_servers:
            print("DNS forwarding warning: No name-servers set under 'system name-server'\n")
        else:
            dns['name_servers'] = dns['name_servers'] + system_name_servers
        conf.set_level(base)

    dns['name_servers'] = bracketize_ipv6_addrs(dns['name_servers'])

    if conf.exists(['listen-address']):
        dns['listen_on'] = conf.return_values(['listen-address'])

    if conf.exists(['dnssec']):
        dns['dnssec'] = conf.return_value(['dnssec'])

    # Add name servers received from DHCP
    if conf.exists(['dhcp']):
        interfaces = []
        interfaces = conf.return_values(['dhcp'])
        hc = hostsd_client()

        for interface in interfaces:
            dhcp_resolvers = hc.get_name_servers(f'dhcp-{interface}')
            dhcpv6_resolvers = hc.get_name_servers(f'dhcpv6-{interface}')

            if dhcp_resolvers:
                dns['name_servers'] = dns['name_servers'] + dhcp_resolvers
            if dhcpv6_resolvers:
                dns['name_servers'] = dns['name_servers'] + dhcpv6_resolvers

    return dns

def bracketize_ipv6_addrs(addrs):
    """Wraps each IPv6 addr in addrs in [], leaving IPv4 addrs untouched."""
    return ['[{0}]'.format(a) if a.count(':') > 1 else a for a in addrs]

def verify(dns):
    # bail out early - looks like removal from running config
    if dns is None:
        return None

    if not dns['listen_on']:
        raise ConfigError(
            "Error: DNS forwarding requires either a listen-address (preferred) or a listen-on option")

    if not dns['allow_from']:
        raise ConfigError(
                "Error: DNS forwarding requires an allow-from network")

    if dns['domains']:
        for domain in dns['domains']:
            if not domain['servers']:
                raise ConfigError(
                    'Error: No server configured for domain {0}'.format(domain['name']))

    return None

def generate(dns):
    # bail out early - looks like removal from running config
    if dns is None:
        return None

    # Prepare Jinja2 template loader from files
    tmpl_path = os.path.join(vyos_data_dir['data'], 'templates', 'dns-forwarding')
    fs_loader = FileSystemLoader(tmpl_path)
    env = Environment(loader=fs_loader, trim_blocks=True)

    tmpl = env.get_template('recursor.conf.tmpl')
    config_text = tmpl.render(dns)
    with open(config_file, 'w') as f:
        f.write(config_text)
    return None

def apply(dns):
    if dns is None:
        # DNS forwarding is removed in the commit
        os.system("systemctl stop pdns-recursor")
        if os.path.isfile(config_file):
            os.unlink(config_file)
    else:
        os.system("systemctl restart pdns-recursor")

if __name__ == '__main__':
    args = parser.parse_args()

    if args.dhclient:
        # There's a big chance it was triggered by a commit still in progress
        # so we need to wait until the new values are in the running config
        wait_for_commit_lock()

    try:
        c = get_config(args)
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
