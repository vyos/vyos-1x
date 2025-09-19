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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import re

from ipaddress import ip_interface
from sys import exit

from vyos.config import Config
from vyos.config import config_dict_merge
from vyos.configverify import verify_vrf
from vyos.configverify import verify_interface_exists
from vyos.template import render
from vyos.utils.file import read_file
from vyos.utils.network import is_addr_assigned
from vyos import ConfigError
from vyos import airbag
from vyos import ipt_netflow
airbag.enable()

ipt_netflow_conf_path = '/etc/modprobe.d/ipt_NETFLOW.conf'

# Variable to store between generate and apply
# whether module configuration was changed
# and module reload is needed
need_reload = True


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'flow-accounting']
    if not conf.exists(base):
        return None

    flow_accounting = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    # We have gathered the dict representation of the CLI, but there are
    # default values which we need to conditionally update into the
    # dictionary retrieved.
    default_values = conf.get_config_defaults(**flow_accounting.kwargs,
                                              recursive=True)

    # delete individual flow type defaults - should only be added if user
    # sets this feature
    flow_type = 'netflow'
    if flow_type not in flow_accounting and flow_type in default_values:
        del default_values[flow_type]

    flow_accounting = config_dict_merge(default_values, flow_accounting)

    return flow_accounting


def verify(flow_config):
    if not flow_config:
        return None

    # Check if at least one interface is configured
    if 'netflow' not in flow_config or 'interface' not in flow_config['netflow']:
        raise ConfigError('Flow accounting requires at least one interface to ' \
                          'be configured!')

    # check that all configured interfaces exists in the system
    for interface in flow_config['netflow']['interface']:
        verify_interface_exists(flow_config, interface, warning_only=True)

    # check if at least one NetFlow collector is configured
    if 'server' not in flow_config['netflow']:
        raise ConfigError('You need to configure at least one NetFlow server!')
    verify_vrf(flow_config)

    # check if vrf is defined for netflow
    netflow_vrf = None
    if 'vrf' in flow_config:
        netflow_vrf = flow_config['vrf']

    # Check if configured netflow server source-address exist in the system
    # Check if configured netflow server source-address matches protocol of server
    # Check if configured netflow server source-interface exists
    for server, data in flow_config['netflow']['server'].items():
        if 'source_address' in data and 'source_interface' in data:
            raise ConfigError(
                f'Configured "netflow server {server}" cannot have both "source-address" and "source-interface" fields'
            )

        if 'source_address' in data:
            if not is_addr_assigned(data['source_address'], netflow_vrf):
                raise ConfigError(
                    f'Configured "netflow server {server} source-address {data["source_address"]}" does not exist on the system!'
                )
            if (
                ip_interface(server).version
                != ip_interface(data['source_address']).version
            ):
                raise ConfigError(
                    f'Configured "netflow server {server} source-address {data["source_address"]}" protocol doesn\'t match server protocol'
                )

        if 'source_interface' in data:
            verify_interface_exists(
                flow_config, data['source_interface'], warning_only=True
            )

    # Check if engine-id compatible with selected protocol version
    if 'engine_id' in flow_config['netflow']:
        v5_filter = '^(\d|[1-9]\d|1\d{2}|2[0-4]\d|25[0-5]):(\d|[1-9]\d|1\d{2}|2[0-4]\d|25[0-5])$'
        v9v10_filter = '^(\d|[1-9]\d{1,8}|[1-3]\d{9}|4[01]\d{8}|42[0-8]\d{7}|429[0-3]\d{6}|4294[0-8]\d{5}|42949[0-5]\d{4}|429496[0-6]\d{3}|4294967[01]\d{2}|42949672[0-8]\d|429496729[0-5])$'
        engine_id = flow_config['netflow']['engine_id']
        version = flow_config['netflow']['version']

        if flow_config['netflow']['version'] == '5':
            regex_filter = re.compile(v5_filter)
            if not regex_filter.search(engine_id):
                raise ConfigError(
                    f'You cannot use NetFlow engine-id "{engine_id}" '
                    f'together with NetFlow protocol version "{version}"!'
                )
        else:
            regex_filter = re.compile(v9v10_filter)
            if not regex_filter.search(flow_config['netflow']['engine_id']):
                raise ConfigError(
                    f'Can not use NetFlow engine-id "{engine_id}" together '
                    f'with NetFlow protocol version "{version}"!'
                )

    # return True if all checks were passed
    return True


def generate(flow_config):
    if not flow_config:
        if os.path.exists(ipt_netflow_conf_path):
            os.unlink(ipt_netflow_conf_path)
        return None

    prev_config = read_file(ipt_netflow_conf_path, defaultonfailure='')

    render(ipt_netflow_conf_path, 'ipt-netflow/ipt_NETFLOW.conf.j2', flow_config)

    new_config = read_file(ipt_netflow_conf_path, defaultonfailure='')

    global need_reload
    need_reload = prev_config != new_config


def apply(flow_config):
    # When reloading module we need to first remove
    # all iptables usage of ipt_NETFLOW
    # When flow_config is disabled everything should be cleaned-up too
    if need_reload or not flow_config:
        ipt_netflow.stop()

    if not flow_config:
        if os.path.exists(ipt_netflow_conf_path):
            os.unlink(ipt_netflow_conf_path)
        return

    ingress_interfaces = []
    egress_interfaces = []

    # configure iptables for defined interfaces
    if 'interface' in flow_config['netflow']:
        ingress_interfaces = flow_config['netflow']['interface']

        # configure egress the same way if configured otherwise remove it
        if 'enable_egress' in flow_config:
            egress_interfaces = ingress_interfaces

    if need_reload:
        ipt_netflow.start(ingress_interfaces, egress_interfaces)
    else:
        ipt_netflow.set_watched_iptables_interfaces(
            ingress_interfaces, egress_interfaces
        )


if __name__ == '__main__':
    try:
        config = get_config()
        verify(config)
        generate(config)
        apply(config)
    except ConfigError as e:
        print(e)
        exit(1)
