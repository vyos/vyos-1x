# Copyright 2021-2024 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

# T3619: mirror Linux Kernel defaults for ethernet offloading options into VyOS
#        CLI. See https://vyos.dev/T3619#102254 for all the details.
# T3787: Remove deprecated UDP fragmentation offloading option
# T6006: add to activation-scripts: migration-scripts/interfaces/20-to-21
# T6716: Honor the configured offload settings and don't automatically add
#        them to the config if the kernel has them set (unless its a live boot)

from vyos.ethtool import Ethtool
from vyos.configtree import ConfigTree
from vyos.system.image import is_live_boot

def activate(config: ConfigTree):
    base = ['interfaces', 'ethernet']

    if not config.exists(base):
        return

    for ifname in config.list_nodes(base):
        eth = Ethtool(ifname)

        # If GRO is enabled by the Kernel - we reflect this on the CLI. If GRO is
        # enabled via CLI but not supported by the NIC - we remove it from the CLI
        configured = config.exists(base + [ifname, 'offload', 'gro'])
        enabled, fixed = eth.get_generic_receive_offload()
        if configured and fixed:
            config.delete(base + [ifname, 'offload', 'gro'])
        elif is_live_boot() and enabled and not fixed:
            config.set(base + [ifname, 'offload', 'gro'])

        # If GSO is enabled by the Kernel - we reflect this on the CLI. If GSO is
        # enabled via CLI but not supported by the NIC - we remove it from the CLI
        configured = config.exists(base + [ifname, 'offload', 'gso'])
        enabled, fixed = eth.get_generic_segmentation_offload()
        if configured and fixed:
            config.delete(base + [ifname, 'offload', 'gso'])
        elif is_live_boot() and enabled and not fixed:
            config.set(base + [ifname, 'offload', 'gso'])

        # If LRO is enabled by the Kernel - we reflect this on the CLI. If LRO is
        # enabled via CLI but not supported by the NIC - we remove it from the CLI
        configured = config.exists(base + [ifname, 'offload', 'lro'])
        enabled, fixed = eth.get_large_receive_offload()
        if configured and fixed:
            config.delete(base + [ifname, 'offload', 'lro'])
        elif is_live_boot() and enabled and not fixed:
            config.set(base + [ifname, 'offload', 'lro'])

        # If SG is enabled by the Kernel - we reflect this on the CLI. If SG is
        # enabled via CLI but not supported by the NIC - we remove it from the CLI
        configured = config.exists(base + [ifname, 'offload', 'sg'])
        enabled, fixed = eth.get_scatter_gather()
        if configured and fixed:
            config.delete(base + [ifname, 'offload', 'sg'])
        elif is_live_boot() and enabled and not fixed:
            config.set(base + [ifname, 'offload', 'sg'])

        # If TSO is enabled by the Kernel - we reflect this on the CLI. If TSO is
        # enabled via CLI but not supported by the NIC - we remove it from the CLI
        configured = config.exists(base + [ifname, 'offload', 'tso'])
        enabled, fixed = eth.get_tcp_segmentation_offload()
        if configured and fixed:
            config.delete(base + [ifname, 'offload', 'tso'])
        elif is_live_boot() and enabled and not fixed:
            config.set(base + [ifname, 'offload', 'tso'])

        # Remove deprecated UDP fragmentation offloading option
        if config.exists(base + [ifname, 'offload', 'ufo']):
            config.delete(base + [ifname, 'offload', 'ufo'])

        # Also while processing the interface configuration, not all adapters support
        # changing the speed and duplex settings. If the desired speed and duplex
        # values do not work for the NIC driver, we change them back to the default
        # value of "auto" - which will be applied if the CLI node is deleted.
        speed_path = base + [ifname, 'speed']
        duplex_path = base + [ifname, 'duplex']
        # speed and duplex must always be set at the same time if not set to "auto"
        if config.exists(speed_path) and config.exists(duplex_path):
            speed = config.return_value(speed_path)
            duplex = config.return_value(duplex_path)
            if speed != 'auto' and duplex != 'auto':
                if not eth.check_speed_duplex(speed, duplex):
                    config.delete(speed_path)
                    config.delete(duplex_path)

        # Also while processing the interface configuration, not all adapters support
        # changing disabling flow-control - or change this setting. If disabling
        # flow-control is not supported by the NIC, we remove the setting from CLI
        flow_control_path = base + [ifname, 'disable-flow-control']
        if config.exists(flow_control_path):
            if not eth.check_flow_control():
                config.delete(flow_control_path)
