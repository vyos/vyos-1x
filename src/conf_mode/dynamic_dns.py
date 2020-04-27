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
from stat import S_IRUSR, S_IWUSR

from vyos.config import Config
from vyos import ConfigError
from vyos.util import call
from vyos.template import render

config_file = r'/run/ddclient/ddclient.conf'

# Mapping of service name to service protocol
default_service_protocol = {
    'afraid': 'freedns',
    'changeip': 'changeip',
    'cloudflare': 'cloudflare',
    'dnspark': 'dnspark',
    'dslreports': 'dslreports1',
    'dyndns': 'dyndns2',
    'easydns': 'easydns',
    'namecheap': 'namecheap',
    'noip': 'noip',
    'sitelutions': 'sitelutions',
    'zoneedit': 'zoneedit1'
}

default_config_data = {
    'interfaces': [],
    'deleted': False
}

def get_config():
    dyndns = deepcopy(default_config_data)
    conf = Config()
    base_level = ['service', 'dns', 'dynamic']

    if not conf.exists(base_level):
        dyndns['deleted'] = True
        return dyndns

    for interface in conf.list_nodes(base_level + ['interface']):
        node = {
            'interface': interface,
            'rfc2136': [],
            'service': [],
            'web_skip': '',
            'web_url': ''
        }

        # set config level to e.g. "service dns dynamic interface eth0"
        conf.set_level(base_level + ['interface', interface])
        # Handle RFC2136 - Dynamic Updates in the Domain Name System
        for rfc2136 in conf.list_nodes(['rfc2136']):
            rfc = {
                'name': rfc2136,
                'keyfile': '',
                'record': [],
                'server': '',
                'ttl': '600',
                'zone': ''
            }

            # set config level
            conf.set_level(base_level + ['interface', interface, 'rfc2136', rfc2136])

            if conf.exists(['key']):
                rfc['keyfile'] = conf.return_value(['key'])

            if conf.exists(['record']):
                rfc['record'] = conf.return_values(['record'])

            if conf.exists(['server']):
                rfc['server'] = conf.return_value(['server'])

            if conf.exists(['ttl']):
                rfc['ttl'] = conf.return_value(['ttl'])

            if conf.exists(['zone']):
                rfc['zone'] = conf.return_value(['zone'])

            node['rfc2136'].append(rfc)

        # set config level to e.g. "service dns dynamic interface eth0"
        conf.set_level(base_level + ['interface', interface])
        # Handle DynDNS service providers
        for service in conf.list_nodes(['service']):
            srv = {
                'provider': service,
                'host': [],
                'login': '',
                'password': '',
                'protocol': '',
                'server': '',
                'custom' : False,
                'zone' : ''
            }

            # set config level
            conf.set_level(base_level + ['interface', interface, 'service', service])

            # preload protocol from default service mapping
            if service in default_service_protocol.keys():
                srv['protocol'] = default_service_protocol[service]
            else:
                srv['custom'] = True

            if conf.exists(['login']):
                srv['login'] = conf.return_value(['login'])

            if conf.exists(['host-name']):
                srv['host'] = conf.return_values(['host-name'])

            if conf.exists(['protocol']):
                srv['protocol'] = conf.return_value(['protocol'])

            if conf.exists(['password']):
                srv['password'] = conf.return_value(['password'])

            if conf.exists(['server']):
                srv['server'] = conf.return_value(['server'])

            if conf.exists(['zone']):
                srv['zone'] = conf.return_value(['zone'])
            elif srv['provider'] == 'cloudflare':
                # default populate zone entry with bar.tld if
                # host-name is foo.bar.tld
                srv['zone'] = srv['host'][0].split('.',1)[1]

            node['service'].append(srv)

        # Set config back to appropriate level for these options
        conf.set_level(base_level + ['interface', interface])

        # Additional settings in CLI
        if conf.exists(['use-web', 'skip']):
            node['web_skip'] = conf.return_value(['use-web', 'skip'])

        if conf.exists(['use-web', 'url']):
            node['web_url'] = conf.return_value(['use-web', 'url'])

        # set config level back to top level
        conf.set_level(base_level)

        dyndns['interfaces'].append(node)

    return dyndns

def verify(dyndns):
    # bail out early - looks like removal from running config
    if dyndns['deleted']:
        return None

    # A 'node' corresponds to an interface
    for node in dyndns['interfaces']:

        # RFC2136 - configuration validation
        for rfc2136 in node['rfc2136']:
            if not rfc2136['record']:
                raise ConfigError('Set key for service "{0}" to send DDNS updates for interface "{1}"'.format(rfc2136['name'], node['interface']))

            if not rfc2136['zone']:
                raise ConfigError('Set zone for service "{0}" to send DDNS updates for interface "{1}"'.format(rfc2136['name'], node['interface']))

            if not rfc2136['keyfile']:
                raise ConfigError('Set keyfile for service "{0}" to send DDNS updates for interface "{1}"'.format(rfc2136['name'], node['interface']))
            else:
                if not os.path.isfile(rfc2136['keyfile']):
                    raise ConfigError('Keyfile for service "{0}" to send DDNS updates for interface "{1}" does not exist'.format(rfc2136['name'], node['interface']))

            if not rfc2136['server']:
                raise ConfigError('Set server for service "{0}" to send DDNS updates for interface "{1}"'.format(rfc2136['name'], node['interface']))

        # DynDNS service provider - configuration validation
        for service in node['service']:
            if not service['host']:
                raise ConfigError('Set host-name for service "{0}" to send DDNS updates for interface "{1}"'.format(service['provider'], node['interface']))

            if not service['login']:
                raise ConfigError('Set login for service "{0}" to send DDNS updates for interface "{1}"'.format(service['provider'], node['interface']))

            if not service['password']:
                raise ConfigError('Set password for service "{0}" to send DDNS updates for interface "{1}"'.format(service['provider'], node['interface']))

            if service['custom'] is True:
                if not service['protocol']:
                    raise ConfigError('Set protocol for service "{0}" to send DDNS updates for interface "{1}"'.format(service['provider'], node['interface']))

                if not service['server']:
                    raise ConfigError('Set server for service "{0}" to send DDNS updates for interface "{1}"'.format(service['provider'], node['interface']))

            if service['zone']:
                if service['provider'] != 'cloudflare':
                    raise ConfigError('Zone option not allowed for "{0}", it can only be used for CloudFlare'.format(service['provider']))

    return None

def generate(dyndns):
    # bail out early - looks like removal from running config
    if dyndns['deleted']:
        return None

    render(config_file, 'dynamic-dns/ddclient.conf.tmpl', dyndns)

    # Config file must be accessible only by its owner
    os.chmod(config_file, S_IRUSR | S_IWUSR)

    return None

def apply(dyndns):
    if dyndns['deleted']:
        call('systemctl stop ddclient.service')
        if os.path.exists(config_file):
            os.unlink(config_file)

    else:
        call('systemctl restart ddclient.service')

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
