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
from vyos.vpp.ipfix import IPFIX
from vyos.vpp.utils import cli_ifaces_list
from vyos.vpp.utils import vpp_iface_name_transform


def get_config(config=None) -> dict:
    if config:
        conf = config
    else:
        conf = Config()

    base = ['vpp', 'ipfix']

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

    # Verify that at least one interface is configured
    if 'interface' not in config or not config['interface']:
        raise ConfigError(
            'At least one interface must be configured for IPFIX monitoring'
        )

    # Verify that all interfaces specified exist in VPP
    for interface in config['interface']:
        if interface not in config['vpp_ifaces']:
            raise ConfigError(
                f'{interface} must be a VPP interface for IPFIX monitoring'
            )

    # Verify that at least one collector is configured
    if 'collector' not in config:
        raise ConfigError('At least one IPFIX collector must be configured')

    # Enforce that only one collector is configured (VPP limitation)
    if len(config['collector']) > 1:
        raise ConfigError('Only one IPFIX collector can be configured')

    # Verify that source_address is specified
    for c, c_conf in config.get('collector', {}).items():
        if 'source_address' not in c_conf:
            raise ConfigError(f'Source address must be specified for collector {c}')

    # Verify active timeout is not greater than inactive timeout
    if 'active_timeout' in config and 'inactive_timeout' in config:
        active_timeout = int(config['active_timeout'])
        inactive_timeout = int(config['inactive_timeout'])

        if active_timeout > inactive_timeout:
            raise ConfigError(
                f'Active timeout ({active_timeout}) cannot be greater than inactive timeout ({inactive_timeout})'
            )


def generate(config):
    # No templates to render for IPFIX
    pass


def apply(config):
    i = IPFIX()

    # Remove collectors
    for c, c_conf in config.get('effective', {}).get('collector', {}).items():
        i.ipfix_exporter_delete()

    # Remove interfaces
    for iface, iface_conf in config.get('effective', {}).get('interface', {}).items():
        iface = vpp_iface_name_transform(iface)
        direction = iface_conf.get('direction')
        which = iface_conf.get('flow_variant')
        i.flowprobe_interface_delete(iface, direction=direction, which=which)

    if 'remove' in config:
        return None

    active_timeout = config.get('active_timeout')
    inactive_timeout = config.get('inactive_timeout')
    flowprobe_record = config.get('flowprobe_record')

    # Flowprobe params
    i.flowprobe_set_params(
        active_timer=int(active_timeout),
        passive_timer=int(inactive_timeout),
        record_flags=list(flowprobe_record),
    )

    # Collectors
    for c, c_conf in config.get('collector', {}).items():
        collector_address = c
        collector_port = c_conf.get('port')
        src_address = c_conf.get('source_address')
        template_interval = c_conf.get('template_interval')
        path_mtu = c_conf.get('path_mtu')
        udp_checksum = 'udp_checksum' in c_conf

        i.collector_address = collector_address
        i.src_address = src_address
        i.collector_port = int(collector_port)
        i.template_interval = int(template_interval)
        i.path_mtu = int(path_mtu)
        i.udp_checksum = udp_checksum
        # VRF support is not currently implemented; exporter is always configured in the default VRF (0).
        # Consider adding VRF support in the future if needed.
        i.vrf_id = 0

        i.set_ipfix_exporter()

    # Interfaces
    if 'interface' in config:
        for iface, iface_config in config.get('interface', {}).items():
            iface = vpp_iface_name_transform(iface)
            direction = iface_config.get('direction')
            which = iface_config.get('flow_variant')

            i.flowprobe_interface_add(iface, direction=direction, which=which)


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
