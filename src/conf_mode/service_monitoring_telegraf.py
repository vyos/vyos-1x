#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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
import json

from sys import exit
from shutil import rmtree

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.template import render
from vyos.util import call
from vyos.util import chown
from vyos.util import cmd
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()


base_dir = '/run/telegraf'
cache_dir = f'/etc/telegraf/.cache'
config_telegraf = f'{base_dir}/vyos-telegraf.conf'
custom_scripts_dir = '/etc/telegraf/custom_scripts'
syslog_telegraf = '/etc/rsyslog.d/50-telegraf.conf'
systemd_telegraf_service = '/etc/systemd/system/vyos-telegraf.service'
systemd_telegraf_override_dir = '/etc/systemd/system/vyos-telegraf.service.d'
systemd_override = f'{systemd_telegraf_override_dir}/10-override.conf'


def get_nft_filter_chains():
    """
    Get nft chains for table filter
    """
    nft = cmd('nft --json list table ip filter')
    nft = json.loads(nft)
    chain_list = []

    for output in nft['nftables']:
        if 'chain' in output:
            chain = output['chain']['name']
            chain_list.append(chain)

    return chain_list

def get_config(config=None):

    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'monitoring', 'telegraf']
    if not conf.exists(base):
        return None

    monitoring = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True)

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)
    monitoring = dict_merge(default_values, monitoring)

    monitoring['nft_chains'] = get_nft_filter_chains()
    monitoring['custom_scripts_dir'] = custom_scripts_dir

    return monitoring

def verify(monitoring):
    # bail out early - looks like removal from running config
    if not monitoring:
        return None

    if 'authentication' not in monitoring or \
       'organization' not in monitoring['authentication'] or \
       'token' not in monitoring['authentication']:
        raise ConfigError(f'Authentication "organization and token" are mandatory!')

    if 'url' not in monitoring:
        raise ConfigError(f'Monitoring "url" is mandatory!')

    return None

def generate(monitoring):
    if not monitoring:
        # Delete config and systemd files
        config_files = [config_telegraf, systemd_telegraf_service, systemd_override, syslog_telegraf]
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

    # Create systemd override dir
    if not os.path.exists(systemd_telegraf_override_dir):
        os.mkdir(systemd_telegraf_override_dir)

    # Create custome scripts dir
    if not os.path.exists(custom_scripts_dir):
        os.mkdir(custom_scripts_dir)

    # Render telegraf configuration and systemd override
    render(config_telegraf, 'monitoring/telegraf.tmpl', monitoring)
    render(systemd_telegraf_service, 'monitoring/systemd_vyos_telegraf_service.tmpl', monitoring)
    render(systemd_override, 'monitoring/override.conf.tmpl', monitoring, permission=0o640)
    render(syslog_telegraf, 'monitoring/syslog_telegraf.tmpl', monitoring)

    chown(base_dir, 'telegraf', 'telegraf')

    return None

def apply(monitoring):
    # Reload systemd manager configuration
    call('systemctl daemon-reload')
    if monitoring:
        call('systemctl restart vyos-telegraf.service')
    else:
        call('systemctl stop vyos-telegraf.service')
    # Telegraf include custom rsyslog config changes
    call('systemctl restart rsyslog')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
