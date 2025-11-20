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

import sys
import typing

from tabulate import tabulate
from vyos.vpp import VPPControl
from vyos.configquery import ConfigTreeQuery
import vyos.opmode


class VPPShow:
    def __init__(self):
        self.config = ConfigTreeQuery()
        self.vpp = VPPControl()

    # -----------------------------
    # IPFIX Interfaces
    # -----------------------------
    def _get_ipfix_interfaces_raw(self) -> typing.List[dict]:
        interfaces = self.vpp.api.flowprobe_interface_dump()
        index_map = {
            i.sw_if_index: i.interface_name for i in self.vpp.api.sw_interface_dump()
        }

        return [
            {
                'interface': index_map.get(e.sw_if_index, f'if{e.sw_if_index}'),
                'sw_if_index': e.sw_if_index,
                'which': e.which.name.replace('FLOWPROBE_WHICH_', '').lower(),
                'direction': e.direction.name.replace(
                    'FLOWPROBE_DIRECTION_', ''
                ).lower(),
            }
            for e in interfaces
        ]

    def _show_ipfix_interfaces_formatted(self, data: typing.List[dict]) -> str:
        if not data:
            return 'No flowprobe interfaces configured.'
        table_data = [
            {
                'Interface': d['interface'],
                'VppIfIndex': d['sw_if_index'],
                'Flow-variant': d['which'],
                'Direction': d['direction'],
            }
            for d in data
        ]
        return tabulate(table_data, headers='keys', tablefmt='simple')

    def ipfix_interfaces(self, raw: bool):
        base = ['vpp', 'ipfix', 'interface']
        if not self.config.exists(base):
            raise vyos.opmode.UnconfiguredSubsystem(
                'vpp ipfix interface is not configured'
            )

        data = self._get_ipfix_interfaces_raw()
        return data if raw else self._show_ipfix_interfaces_formatted(data)

    # -----------------------------
    # IPFIX Collectors
    # -----------------------------
    def _get_ipfix_collectors_raw(self) -> typing.List[dict]:
        _, collectors = self.vpp.api.ipfix_all_exporter_get()
        return [
            {
                'collector_address': str(c.collector_address),
                'collector_port': c.collector_port,
                'src_address': str(c.src_address),
                'vrf_id': c.vrf_id,
                'path_mtu': c.path_mtu,
                'template_interval': c.template_interval,
                'udp_checksum': bool(c.udp_checksum),
            }
            for c in collectors
        ]

    def _show_ipfix_collectors_formatted(self, data: typing.List[dict]) -> str:
        if not data:
            return 'No IPFIX collectors configured.'
        table_data = [
            {
                'Collector': f"{d['collector_address']}:{d['collector_port']}",
                'Source': d['src_address'],
                'VRF': d['vrf_id'],
                'MTU': d['path_mtu'],
                'Template Intvl': d['template_interval'],
                'UDP Cksum': 'on' if d['udp_checksum'] else 'off',
            }
            for d in data
        ]
        return tabulate(table_data, headers='keys', tablefmt='simple')

    def ipfix_collectors(self, raw: bool):
        base = ['vpp', 'ipfix', 'collector']
        if not self.config.exists(base):
            raise vyos.opmode.UnconfiguredSubsystem(
                'vpp ipfix collector is not configured'
            )

        data = self._get_ipfix_collectors_raw()
        return data if raw else self._show_ipfix_collectors_formatted(data)

    # -----------------------------
    # IPFIX table
    # -----------------------------
    def _get_ipfix_table_raw(self):
        # VPP does not have API call to get this data
        data = self.vpp.cli_cmd('show flowprobe table')
        return [data.reply]

    def _show_ipfix_table_formatted(self) -> str:
        data = self.vpp.cli_cmd('show flowprobe table')
        return data.reply

    def ipfix_table(self, raw: bool):
        base = ['vpp', 'ipfix', 'collector']
        if not self.config.exists(base):
            raise vyos.opmode.UnconfiguredSubsystem(
                'vpp ipfix collector is not configured'
            )

        data = self._get_ipfix_table_raw()
        return data if raw else self._show_ipfix_table_formatted()


# -----------------------------
# VyOS IPFIX op-mode entries
# -----------------------------
def show_ipfix_interfaces(raw: bool):
    return VPPShow().ipfix_interfaces(raw)


def show_ipfix_collectors(raw: bool):
    return VPPShow().ipfix_collectors(raw)


def show_ipfix_table(raw: bool):
    return VPPShow().ipfix_table(raw)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
