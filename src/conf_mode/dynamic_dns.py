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
from vyos.template import render
from vyos.util import call
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

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

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base_level = ['service', 'dns', 'dynamic']
    if not conf.exists(base_level):
        return None

    dyndns = conf.get_config_dict(base_level, key_mangling=('-', '_'), get_first_key=True)

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    for interface in dyndns['interface']:
        if 'service' in dyndns['interface'][interface]:
            # 'Autodetect' protocol used by DynDNS service
            for service in dyndns['interface'][interface]['service']:
                if service in default_service_protocol:
                    dyndns['interface'][interface]['service'][service].update(
                        {'protocol' : default_service_protocol.get(service)})
                else:
                    dyndns['interface'][interface]['service'][service].update(
                        {'custom': ''})

        if 'rfc2136' in dyndns['interface'][interface]:
            default_values = defaults(base_level + ['interface', 'rfc2136'])
            for rfc2136 in dyndns['interface'][interface]['rfc2136']:
                dyndns['interface'][interface]['rfc2136'][rfc2136] = dict_merge(
                    default_values, dyndns['interface'][interface]['rfc2136'][rfc2136])

    return dyndns

def verify(dyndns):
    # bail out early - looks like removal from running config
    if not dyndns:
        return None

    # A 'node' corresponds to an interface
    if 'interface' not in dyndns:
        return None

    for interface in dyndns['interface']:
        # RFC2136 - configuration validation
        if 'rfc2136' in dyndns['interface'][interface]:
            for rfc2136, config in dyndns['interface'][interface]['rfc2136'].items():

                for tmp in ['record', 'zone', 'server', 'key']:
                    if tmp not in config:
                        raise ConfigError(f'"{tmp}" required for rfc2136 based '
                                          f'DynDNS service on "{interface}"')

                if not os.path.isfile(config['key']):
                    raise ConfigError(f'"key"-file not found for rfc2136 based '
                                      f'DynDNS service on "{interface}"')

        # DynDNS service provider - configuration validation
        if 'service' in dyndns['interface'][interface]:
            for service, config in dyndns['interface'][interface]['service'].items():
                error_msg = f'required for DynDNS service "{service}" on "{interface}"'
                if 'host_name' not in config:
                    raise ConfigError(f'"host-name" {error_msg}')

                if 'login' not in config:
                    raise ConfigError(f'"login" (username) {error_msg}')

                if 'password' not in config:
                    raise ConfigError(f'"password" {error_msg}')

                if 'zone' in config:
                    if service != 'cloudflare':
                        raise ConfigError(f'"zone" option only supported with CloudFlare')

                if 'custom' in config:
                    if 'protocol' not in config:
                        raise ConfigError(f'"protocol" {error_msg}')

                    if 'server' not in config:
                        raise ConfigError(f'"server" {error_msg}')

    return None

def generate(dyndns):
    # bail out early - looks like removal from running config
    if not dyndns:
        return None

    render(config_file, 'dynamic-dns/ddclient.conf.tmpl', dyndns,
           permission=0o600)

    return None

def apply(dyndns):
    if not dyndns:
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
