#
# Copyright (C) VyOS Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from vpp_papi import VppEnum
from vyos.vpp import VPPControl


class IPFIX:
    def __init__(
        self,
        collector_address: str = '0.0.0.0',
        collector_port: int = 4739,
        src_address: str = '0.0.0.0',
        path_mtu: int = 0,
        template_interval: int = 20,
        udp_checksum: bool = False,
        vrf_id: int = 0,
    ):
        self.vpp = VPPControl()
        self.collector_address = collector_address
        self.collector_port = collector_port
        self.src_address = src_address
        self.path_mtu = path_mtu
        self.template_interval = template_interval
        self.udp_checksum = udp_checksum
        self.vrf_id = vrf_id

        # enums mapping
        self.RECORD_FLAGS_MAP = {
            'l2': VppEnum.vl_api_flowprobe_record_flags_t.FLOWPROBE_RECORD_FLAG_L2,
            'l3': VppEnum.vl_api_flowprobe_record_flags_t.FLOWPROBE_RECORD_FLAG_L3,
            'l4': VppEnum.vl_api_flowprobe_record_flags_t.FLOWPROBE_RECORD_FLAG_L4,
        }

        self.WHICH_FLAGS_MAP = {
            'ipv4': VppEnum.vl_api_flowprobe_which_t.FLOWPROBE_WHICH_IP4,
            'ipv6': VppEnum.vl_api_flowprobe_which_t.FLOWPROBE_WHICH_IP6,
            'l2': VppEnum.vl_api_flowprobe_which_t.FLOWPROBE_WHICH_L2,
        }

        self.DIRECTION_MAP = {
            'rx': VppEnum.vl_api_flowprobe_direction_t.FLOWPROBE_DIRECTION_RX,
            'tx': VppEnum.vl_api_flowprobe_direction_t.FLOWPROBE_DIRECTION_TX,
            'both': VppEnum.vl_api_flowprobe_direction_t.FLOWPROBE_DIRECTION_BOTH,
        }

    def ipfix_exporter_delete(self):
        """Delete IPFIX exporter
        https://github.com/FDio/vpp/blob/stable/2506/src/vnet/ipfix-export/ipfix_export.api
        Example:
            from vyos.vpp import ipfix
            i = ipfix.IPFIX()
            i.ipfix_exporter_delete()
        """
        self.vpp.api.set_ipfix_exporter(
            collector_port=0,
            collector_address='0.0.0.0',
            src_address='0.0.0.0',
            path_mtu=0xFFFFFFFF,
            template_interval=0,
            udp_checksum=False,
            vrf_id=4294967295,
        )

    def set_ipfix_exporter(self):
        """Set IPFIX exporter parameters
        Example:
            from vyos.vpp import ipfix
            i = ipfix.IPFIX(collector_address='192.0.2.2', src_address='192.0.2.1', collector_port=2055, template_interval=20, path_mtu=1450)
            i.set_ipfix_exporter()
        """
        self.vpp.api.set_ipfix_exporter(
            collector_port=self.collector_port,
            collector_address=self.collector_address,
            src_address=self.src_address,
            path_mtu=self.path_mtu,
            template_interval=self.template_interval,
            udp_checksum=self.udp_checksum,
            vrf_id=self.vrf_id,
        )

    def flowprobe_interface_add(
        self,
        interface: str,
        direction: str = 'both',
        which: str = 'ipv4',
    ):
        """Add IPFIX flowprobe to interface
        https://github.com/FDio/vpp/blob/stable/2506/src/plugins/flowprobe/flowprobe.api
        Args:
            interface (str): Interface name
            direction (str): Direction of flowprobe ('rx', 'tx', 'both')
            which (str): Which packets to probe ('ipv4', 'ipv6', 'l2')
        Example:
            from vyos.vpp import ipfix
            i = ipfix.IPFIX(collector_address='192.0.2.2', src_address='192.0.2.1', collector_port=2055, template_interval=20, path_mtu=1450)
            i.flowprobe_set_params(record_flags=['l2', 'l3'], active_timer=2, passive_timer=20)
            i.flowprobe_interface_add('eth0')
        """
        sw_if_index = self.vpp.get_sw_if_index(interface)
        direction_flag = self.DIRECTION_MAP.get(direction, self.DIRECTION_MAP['both'])
        which_flag = self.WHICH_FLAGS_MAP.get(which, self.WHICH_FLAGS_MAP['ipv4'])

        self.vpp.api.flowprobe_interface_add_del(
            is_add=True,
            sw_if_index=sw_if_index,
            direction=direction_flag,
            which=which_flag,
        )

    def flowprobe_interface_delete(
        self,
        interface: str,
        direction: str = 'both',
        which: str = 'ipv4',
    ):
        """Delete IPFIX flowprobe from interface
        https://github.com/FDio/vpp/blob/stable/2506/src/plugins/flowprobe/flowprobe.api
        Args:
            interface (str): Interface name
        Example:
            from vyos.vpp import ipfix
            i = ipfix.IPFIX(collector_address='192.0.2.2', src_address='192.0.2.1', collector_port=2055, template_interval=20, path_mtu=1450)
            i.flowprobe_interface_delete('eth0')
        """
        sw_if_index = self.vpp.get_sw_if_index(interface)
        direction_flag = self.DIRECTION_MAP.get(direction, self.DIRECTION_MAP['both'])
        which_flag = self.WHICH_FLAGS_MAP.get(which, self.WHICH_FLAGS_MAP['ipv4'])

        self.vpp.api.flowprobe_interface_add_del(
            is_add=False,
            sw_if_index=sw_if_index,
            direction=direction_flag,
            which=which_flag,
        )

    def flowprobe_set_params(
        self,
        active_timer: int = 15,
        passive_timer: int = 120,
        record_flags: list = None,
    ):
        """Set IPFIX flowprobe parameters

        Args:
            active_timer (int): Active timer in seconds
            passive_timer (int): Passive timer in seconds
            record_flags: Record flags as list of 'l2', 'l3', 'l4'
                Examples: ['l2'], ['l2', 'l3'], ['l2', 'l3', 'l4']
        Example:
            from vyos.vpp import ipfix
            i = ipfix.IPFIX(collector_address='192.0.2.2', src_address='192.0.2.1', collector_port=2055, template_interval=20, path_mtu=1450)
            i.flowprobe_set_params(record_flags=['l2', 'l3'], active_timer=10, passive_timer=30)
            i.flowprobe_interface_add('eth0')
        """
        if record_flags is None:
            record_flags = ['l2', 'l3', 'l4']
        # Calculate combined flags
        record_flag = 0
        for flag in record_flags:
            record_flag |= self.RECORD_FLAGS_MAP[flag]

        self.vpp.api.flowprobe_set_params(
            active_timer=active_timer,
            passive_timer=passive_timer,
            record_flags=record_flag,
        )
