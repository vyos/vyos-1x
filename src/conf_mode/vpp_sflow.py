#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from vyos import ConfigError
from vyos.config import Config
from vyos.vpp.utils import cli_ifaces_list
from vyos.vpp.sflow import SFlow


def get_config(config=None) -> dict:
    if config:
        conf = config
    else:
        conf = Config()

    base = ['vpp', 'sflow']

    # Get config_dict with default values
    config = conf.get_config_dict(
        base,
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_defaults=True,
        with_recursive_defaults=True,
    )

    # Get effective config as we need full dictionary for deletion
    effective_config = conf.get_config_dict(
        base,
        key_mangling=('-', '_'),
        effective=True,
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    # Get system sflow configuration to check for server
    system_sflow = conf.get_config_dict(
        ['system', 'sflow'],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_recursive_defaults=True,
    )

    if system_sflow:
        config['system_sflow'] = system_sflow

    if effective_config:
        config.update({'effective': effective_config})

    if not conf.exists(base):
        config['remove'] = True
        return config

    # Add list of VPP interfaces to the config
    config.update({'vpp_ifaces': cli_ifaces_list(conf)})

    return config


def verify(config):
    if 'remove' in config:
        return None

    # Check if interface section exists
    if 'interface' not in config:
        raise ConfigError('Interfaces must be configured for sFlow')

    # Verify that all interfaces specified exist in VPP
    for interface in config['interface']:
        if interface not in config['vpp_ifaces']:
            raise ConfigError(
                f'{interface} must be a VPP interface for sFlow monitoring'
            )

    # Verify that system sflow has enable-vpp defined
    if 'system_sflow' not in config or 'vpp' not in config.get('system_sflow', {}):
        raise ConfigError(
            '"sflow vpp" must be defined under system sflow configuration'
        )


def generate(config):
    # No templates to render for sFlow
    pass


def apply(config):
    s = SFlow()

    # Disable sFlow on deleted interface
    for interface in config.get('effective', {}).get('interface', []):
        if interface not in config.get('interface', []):
            s.disable_sflow(interface)

    if 'remove' in config:
        return None

    # Configure sample rate
    if 'sampling_rate' in config.get('system_sflow', {}):
        s.set_sampling_rate(int(config['system_sflow']['sampling_rate']))

    # Configure polling interval
    if 'polling' in config.get('system_sflow', {}):
        s.set_polling_interval(int(config['system_sflow']['polling']))

    # Configure header bytes
    if 'header_bytes' in config:
        s.set_header_bytes(int(config['header_bytes']))

    # Configure interfaces
    for interface in config.get('interface', []):
        s.enable_sflow(interface)


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
