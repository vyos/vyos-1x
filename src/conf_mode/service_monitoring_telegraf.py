#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
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
import socket
import json

from sys import exit
from shutil import rmtree

from vyos.config import Config
from vyos.configdict import is_node_changed
from vyos.configverify import verify_vrf
from vyos.ifconfig import Section
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.permission import chown
from vyos.utils.process import cmd
from vyos import ConfigError
from vyos import airbag
airbag.enable()

cache_dir = f'/etc/telegraf/.cache'
config_telegraf = f'/run/telegraf/telegraf.conf'
custom_scripts_dir = '/etc/telegraf/custom_scripts'
syslog_telegraf = '/etc/rsyslog.d/50-telegraf.conf'
systemd_override = '/run/systemd/system/telegraf.service.d/10-override.conf'

def get_nft_filter_chains():
    """ Get nft chains for table filter """
    try:
        nft = cmd('nft --json list table ip vyos_filter')
    except Exception:
        print('nft table ip vyos_filter not found')
        return []
    nft = json.loads(nft)
    chain_list = []

    for output in nft['nftables']:
        if 'chain' in output:
            chain = output['chain']['name']
            chain_list.append(chain)

    return chain_list

def get_hostname() -> str:
    try:
        hostname = socket.getfqdn()
    except socket.gaierror:
        hostname = socket.gethostname()
    return hostname

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'monitoring', 'telegraf']
    if not conf.exists(base):
        return None

    monitoring = conf.get_config_dict(base, key_mangling=('-', '_'),
                                      get_first_key=True,
                                      no_tag_node_value_mangle=True)

    tmp = is_node_changed(conf, base + ['vrf'])
    if tmp: monitoring.update({'restart_required': {}})

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    monitoring = conf.merge_defaults(monitoring, recursive=True)

    monitoring['custom_scripts_dir'] = custom_scripts_dir
    monitoring['hostname'] = get_hostname()
    monitoring['interfaces_ethernet'] = Section.interfaces('ethernet', vlan=False)
    if conf.exists('firewall'):
        monitoring['nft_chains'] = get_nft_filter_chains()

    # Redefine azure group-metrics 'single-table' and 'table-per-metric'
    if 'azure_data_explorer' in monitoring:
        if 'single-table' in monitoring['azure_data_explorer']['group_metrics']:
            monitoring['azure_data_explorer']['group_metrics'] = 'SingleTable'
        else:
            monitoring['azure_data_explorer']['group_metrics'] = 'TablePerMetric'
        # Set azure env
        if 'authentication' in monitoring['azure_data_explorer']:
            auth_config = monitoring['azure_data_explorer']['authentication']
            if {'client_id', 'client_secret', 'tenant_id'} <= set(auth_config):
                os.environ['AZURE_CLIENT_ID'] = auth_config['client_id']
                os.environ['AZURE_CLIENT_SECRET'] = auth_config['client_secret']
                os.environ['AZURE_TENANT_ID'] = auth_config['tenant_id']

    # Ignore default XML values if config doesn't exists
    # Delete key from dict
    if not conf.exists(base + ['influxdb']):
        del monitoring['influxdb']

    if not conf.exists(base + ['prometheus-client']):
        del monitoring['prometheus_client']

    if not conf.exists(base + ['azure-data-explorer']):
        del monitoring['azure_data_explorer']

    if not conf.exists(base + ['loki']):
        del monitoring['loki']

    return monitoring

def verify(monitoring):
    # bail out early - looks like removal from running config
    if not monitoring:
        return None

    verify_vrf(monitoring)

    # Verify influxdb
    if 'influxdb' in monitoring:
        if 'authentication' not in monitoring['influxdb'] or \
           'organization' not in monitoring['influxdb']['authentication'] or \
           'token' not in monitoring['influxdb']['authentication']:
            raise ConfigError(f'influxdb authentication "organization and token" are mandatory!')

        if 'url' not in monitoring['influxdb']:
            raise ConfigError(f'Monitoring influxdb "url" is mandatory!')

    # Verify azure-data-explorer
    if 'azure_data_explorer' in monitoring:
        if 'authentication' not in monitoring['azure_data_explorer'] or \
           'client_id' not in monitoring['azure_data_explorer']['authentication'] or \
           'client_secret' not in monitoring['azure_data_explorer']['authentication'] or \
           'tenant_id' not in monitoring['azure_data_explorer']['authentication']:
            raise ConfigError(f'Authentication "client-id, client-secret and tenant-id" are mandatory!')

        if 'database' not in monitoring['azure_data_explorer']:
            raise ConfigError(f'Monitoring "database" is mandatory!')

        if 'url' not in monitoring['azure_data_explorer']:
            raise ConfigError(f'Monitoring "url" is mandatory!')

        if monitoring['azure_data_explorer']['group_metrics'] == 'SingleTable' and \
            'table' not in monitoring['azure_data_explorer']:
             raise ConfigError(f'Monitoring "table" name for single-table mode is mandatory!')

    # Verify Splunk
    if 'splunk' in monitoring:
        if 'authentication' not in monitoring['splunk'] or \
           'token' not in monitoring['splunk']['authentication']:
            raise ConfigError(f'Authentication "organization and token" are mandatory!')

        if 'url' not in monitoring['splunk']:
            raise ConfigError(f'Monitoring splunk "url" is mandatory!')

    # Verify Loki
    if 'loki' in monitoring:
        if 'url' not in monitoring['loki']:
            raise ConfigError(f'Monitoring loki "url" is mandatory!')
        if 'authentication' in monitoring['loki']:
            if (
                'username' not in monitoring['loki']['authentication']
                or 'password' not in monitoring['loki']['authentication']
            ):
                raise ConfigError(
                    f'Authentication "username" and "password" are mandatory!'
                )

    return None

def generate(monitoring):
    if not monitoring:
        # Delete config and systemd files
        config_files = [config_telegraf, systemd_override, syslog_telegraf]
        for file in config_files:
            if os.path.isfile(file):
                os.unlink(file)

        # Delete old directories
        if os.path.isdir(cache_dir):
            rmtree(cache_dir, ignore_errors=True)

        return None

    # Create telegraf cache dir
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    chown(cache_dir, 'telegraf', 'telegraf')

    # Create custome scripts dir
    if not os.path.exists(custom_scripts_dir):
        os.mkdir(custom_scripts_dir)

    # Render telegraf configuration and systemd override
    render(config_telegraf, 'telegraf/telegraf.j2', monitoring, user='telegraf', group='telegraf')
    render(systemd_override, 'telegraf/override.conf.j2', monitoring)
    render(syslog_telegraf, 'telegraf/syslog_telegraf.j2', monitoring)

    return None

def apply(monitoring):
    # Reload systemd manager configuration
    systemd_service = 'telegraf.service'
    call('systemctl daemon-reload')
    if not monitoring:
        call(f'systemctl stop {systemd_service}')
        return

    # we need to restart the service if e.g. the VRF name changed
    systemd_action = 'reload-or-restart'
    if 'restart_required' in monitoring:
        systemd_action = 'restart'

    call(f'systemctl {systemd_action} {systemd_service}')

    # Telegraf include custom rsyslog config changes
    call('systemctl reload-or-restart rsyslog')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
