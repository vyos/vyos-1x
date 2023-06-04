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

# Protocols that require zone
zone_allowed = ['cloudflare', 'godaddy', 'hetzner', 'gandi', 'nfsn']

# Protocols that do not require username
username_unnecessary = ['1984', 'cloudflare', 'cloudns', 'duckdns', 'freemyip', 'hetzner', 'keysystems', 'njalla']

# Protocols that support both IPv4 and IPv6
dualstack_supported = ['cloudflare', 'dyndns2', 'freedns', 'njalla']

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base_level = ['service', 'dns', 'dynamic']
    if not conf.exists(base_level):
        return None

    dyndns = conf.get_config_dict(base_level, key_mangling=('-', '_'), get_first_key=True)

    for address in dyndns['address']:
        # Apply service specific defaults (stype = ['rfc2136', 'service'])
        for svc_type in dyndns['address'][address]:
            default_values = defaults(base_level + ['address', svc_type])
            for svc_cfg in dyndns['address'][address][svc_type]:
                dyndns['address'][address][svc_type][svc_cfg] = dict_merge(
                    default_values, dyndns['address'][address][svc_type][svc_cfg])

    return dyndns

def verify(dyndns):
    # bail out early - looks like removal from running config
    if not dyndns:
        return None

    for address in dyndns['address']:
        # RFC2136 - configuration validation
        if 'rfc2136' in dyndns['address'][address]:
            for config in dyndns['address'][address]['rfc2136'].values():
                for field in ['host_name', 'zone', 'server', 'key']:
                    if field not in config:
                        raise ConfigError(f'"{field.replace("_", "-")}" is required for RFC2136 '
                                          f'based Dynamic DNS service on "{address}"')

        # Dynamic DNS service provider - configuration validation
        if 'service' in dyndns['address'][address]:
            for service, config in dyndns['address'][address]['service'].items():
                error_msg = f'is required for Dynamic DNS service "{service}" on "{address}"'

                for field in ['host_name', 'password', 'protocol']:
                    if field not in config:
                        raise ConfigError(f'"{field.replace("_", "-")}" {error_msg}')

                if config['protocol'] in zone_allowed and 'zone' not in config:
                        raise ConfigError(f'"zone" {error_msg}')

                if config['protocol'] not in zone_allowed and 'zone' in config:
                        raise ConfigError(f'"{config["protocol"]}" does not support "zone"')

                if config['protocol'] not in username_unnecessary:
                    if 'username' not in config:
                        raise ConfigError(f'"username" {error_msg}')

                if config['ip_version'] == 'both':
                    if config['protocol'] not in dualstack_supported:
                        raise ConfigError(f'"{config["protocol"]}" does not support IPv4 and IPv6 at the same time')
                    # dyndns2 protocol in ddclient honors dual stack only for dyn.com (dyndns.org)
                    if config['protocol'] == 'dyndns2' and 'server' in config and config['server'] != 'members.dyndns.org':
                        raise ConfigError(f'"{config["protocol"]}" for "{config["server"]}" does not support IPv4 and IPv6 at the same time')

    return None

def generate(dyndns):
    # bail out early - looks like removal from running config
    if not dyndns:
        return None

    render(config_file, 'dns-dynamic/ddclient.conf.j2', dyndns)
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