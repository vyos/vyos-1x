#!/usr/bin/env python3
#
# Copyright (C) 2018-2023 VyOS maintainers and contributors
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
from vyos.configverify import verify_interface_exists
from vyos.template import render
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = r'/run/ddclient/ddclient.conf'
systemd_override = r'/run/systemd/system/ddclient.service.d/override.conf'

# Protocols that require zone
zone_necessary = ['cloudflare', 'godaddy', 'hetzner', 'gandi', 'nfsn']

# Protocols that do not require username
username_unnecessary = ['1984', 'cloudflare', 'cloudns', 'duckdns', 'freemyip', 'hetzner', 'keysystems', 'njalla']

# Protocols that support TTL
ttl_supported = ['cloudflare', 'gandi', 'hetzner', 'dnsexit', 'godaddy', 'nfsn']

# Protocols that support both IPv4 and IPv6
dualstack_supported = ['cloudflare', 'dyndns2', 'freedns', 'njalla']

# dyndns2 protocol in ddclient honors dual stack for selective servers
# because of the way it is implemented in ddclient
dyndns_dualstack_servers = ['members.dyndns.org', 'dynv6.com']

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['service', 'dns', 'dynamic']
    if not conf.exists(base):
        return None

    dyndns = conf.get_config_dict(base, key_mangling=('-', '_'),
                                  no_tag_node_value_mangle=True,
                                  get_first_key=True,
                                  with_recursive_defaults=True)

    dyndns['config_file'] = config_file
    return dyndns

def verify(dyndns):
    # bail out early - looks like removal from running config
    if not dyndns or 'address' not in dyndns:
        return None

    for address in dyndns['address']:
        # If dyndns address is an interface, ensure it exists
        if address != 'web':
            verify_interface_exists(address)

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

                if config['protocol'] in zone_necessary and 'zone' not in config:
                    raise ConfigError(f'"zone" {error_msg}')

                if config['protocol'] not in zone_necessary and 'zone' in config:
                    raise ConfigError(f'"{config["protocol"]}" does not support "zone"')

                if config['protocol'] not in username_unnecessary and 'username' not in config:
                    raise ConfigError(f'"username" {error_msg}')

                if config['protocol'] not in ttl_supported and 'ttl' in config:
                    raise ConfigError(f'"{config["protocol"]}" does not support "ttl"')

                if config['ip_version'] == 'both':
                    if config['protocol'] not in dualstack_supported:
                        raise ConfigError(f'"{config["protocol"]}" does not support '
                                          f'both IPv4 and IPv6 at the same time')
                    # dyndns2 protocol in ddclient honors dual stack only for dyn.com (dyndns.org)
                    if config['protocol'] == 'dyndns2' and 'server' in config and config['server'] not in dyndns_dualstack_servers:
                        raise ConfigError(f'"{config["protocol"]}" does not support '
                                          f'both IPv4 and IPv6 at the same time for "{config["server"]}"')

                if {'wait_time', 'expiry_time'} <= config.keys() and int(config['expiry_time']) < int(config['wait_time']):
                        raise ConfigError(f'"expiry-time" must be greater than "wait-time"')

    return None

def generate(dyndns):
    # bail out early - looks like removal from running config
    if not dyndns or 'address' not in dyndns:
        return None

    render(config_file, 'dns-dynamic/ddclient.conf.j2', dyndns, permission=0o600)
    render(systemd_override, 'dns-dynamic/override.conf.j2', dyndns)
    return None

def apply(dyndns):
    systemd_service = 'ddclient.service'
    # Reload systemd manager configuration
    call('systemctl daemon-reload')

    # bail out early - looks like removal from running config
    if not dyndns or 'address' not in dyndns:
        call(f'systemctl stop {systemd_service}')
        if os.path.exists(config_file):
            os.unlink(config_file)
    else:
        call(f'systemctl reload-or-restart {systemd_service}')

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
