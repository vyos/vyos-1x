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
import json
import typing

from tabulate import tabulate
from vyos.vpp import VPPControl
from vyos.configquery import ConfigTreeQuery
import vyos.opmode


NO_INDEX = 0xFFFFFFFF


def _verify(target: typing.Optional[str]):
    """Decorator checks if config for VPP feature exists"""
    from functools import wraps

    target = target.split() if target else []

    def _verify_target(func):
        @wraps(func)
        def _wrapper(*args, **kwargs):
            config = ConfigTreeQuery()
            path = ['vpp'] + target
            if not config.exists(path):
                raise vyos.opmode.UnconfiguredSubsystem(
                    f'"{" ".join(path)}" is not configured'
                )
            return func(*args, **kwargs)

        return _wrapper

    return _verify_target


class VPPShow:
    RX_STATES = {
        0: 'INITIALIZE',
        1: 'PORT_DISABLED',
        2: 'EXPIRED',
        3: 'LACP_DISABLED',
        4: 'DEFAULTED',
        5: 'CURRENT',
    }
    TX_STATES = {0: 'TRANSMIT'}
    MUX_STATES = {
        0: 'DETACHED',
        1: 'WAITING',
        2: 'ATTACHED',
        3: 'COLLECTING_DISTRIBUTING',
    }
    PTX_STATES = {0: 'NO_PERIODIC', 1: 'FAST', 2: 'SLOW', 3: 'PERIODIC_TX'}

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
    # LACP information
    # -----------------------------
    def _get_raw_output(self, data_dump: typing.List[dict]) -> list[dict]:
        data = [json.loads(json.dumps(d._asdict(), default=str)) for d in data_dump]
        return data

    def _get_lacp_raw(self, ifname: typing.Optional[str]) -> list[dict]:
        lacp_dump = self.vpp.api.sw_interface_lacp_dump()
        data = self._get_raw_output(lacp_dump)

        if ifname:
            res = next((d for d in data if d['interface_name'] == ifname), None)
            if not res:
                raise vyos.opmode.IncorrectValue(
                    f'Interface {ifname} is not a member of any LACP bond'
                )
            data = [res]

        return data

    def _get_lacp_info_formatted(self, data):

        def bit(x, n):
            return (x >> n) & 1

        def bits_to_str(x):
            return ' '.join(f'{bit(x, n):3d}' for n in range(7, -1, -1))

        # Headers (exactly like VPP)
        print(f'{"":55} {"actor state":32} {"partner state":32}')
        print(
            'interface name'.ljust(26)
            + 'sw_if_index'.ljust(13)
            + 'bond interface'.ljust(17)
            + 'exp/def/dis/col/syn/agg/tim/act'.ljust(33)
            + 'exp/def/dis/col/syn/agg/tim/act'.ljust(32)
        )

        for d in data:
            iface = d['interface_name']
            sw_if = str(d['sw_if_index'])
            bond_if = d['bond_interface_name']
            actor_bits = bits_to_str(d['actor_state'])
            partner_bits = bits_to_str(d['partner_state'])

            print(
                f'{iface:25} {sw_if:12} {bond_if:16} {actor_bits:32} {partner_bits:32}'
            )

            # LAG ID formatting
            lag_line = (
                f'  LAG ID: '
                f'[({d["actor_system_priority"]:04x},{d["actor_system"].replace(":", "-")},'
                f'{d["actor_key"]:04x},{d["actor_port_priority"]:04x},{d["actor_port_number"]:04x}), '
                f'({d["partner_system_priority"]:04x},{d["partner_system"].replace(":", "-")},'
                f'{d["partner_key"]:04x},{d["partner_port_priority"]:04x},{d["partner_port_number"]:04x})]'
            )
            print(lag_line)

            # State machine line
            print(
                f'  RX-state: {self.RX_STATES[d["rx_state"]]}, '
                f'TX-state: {self.TX_STATES[d["tx_state"]]}, '
                f'MUX-state: {self.MUX_STATES[d["mux_state"]]}, '
                f'PTX-state: {self.PTX_STATES[d["ptx_state"]]}'
            )

    def lacp_info(self, raw: bool, ifname: typing.Optional[str]):
        data = self._get_lacp_raw(ifname)

        if raw:
            return data

        return self._get_lacp_info_formatted(data)

    def lacp_details(self, raw: bool, ifname: typing.Optional[str]) -> str:
        # Check if interface is a part of any LACP bond
        self._get_lacp_raw(ifname)

        # VPP does not have API call to get this data
        cmd_command = f'show lacp{f" {ifname}" if ifname else ""} details'
        data = self.vpp.cli_cmd(cmd_command)

        if raw:
            return [data.reply]

        return data.reply

    # -----------------------------
    # Bridge-domain information
    # -----------------------------
    def _parse_bridge_id(self, ifname: typing.Optional[str]) -> typing.Optional[int]:
        if ifname is None:
            return None

        if not ifname.startswith('br') and not ifname[2:].isdigit():
            raise vyos.opmode.IncorrectValue(
                f'"{ifname}" is not a valid bridge interface name (expected brN)'
            )

        if not self.config.exists(['vpp', 'interfaces', 'bridge', ifname]):
            raise vyos.opmode.IncorrectValue(
                f'Bridge interface {ifname} does not exist'
            )

        return int(ifname[2:])

    def _get_bridge_domain_raw(
        self, bd_id: typing.Optional[int] = None
    ) -> typing.List[dict]:
        # Dump bridge domains
        domains = self.vpp.api.bridge_domain_dump(
            bd_id=bd_id if bd_id is not None else NO_INDEX
        )

        result = []
        for d in domains:
            domain_info = {
                'bd_id': d.bd_id,
                'learning': bool(d.learn),
                'forward': bool(d.forward),
                'uu_flood': bool(d.uu_flood),
                'flood': bool(d.flood),
                'arp_term': bool(d.arp_term),
                'arp_ufwd': bool(d.arp_ufwd),
                'mac_age': d.mac_age,
                'bvi_interface': d.bvi_sw_if_index,
                'n_sw_ifs': d.n_sw_ifs,
                'members': [
                    {
                        'ifname': self.vpp.get_interface_name(m.sw_if_index),
                        'sw_if_index': m.sw_if_index,
                        'shg': m.shg,
                    }
                    for m in d.sw_if_details
                ],
            }
            result.append(domain_info)

        result.sort(key=lambda x: x['bd_id'])

        return result

    def _show_bridge_domain_formatted(self, data: typing.List[dict]) -> str:
        if not data:
            return 'No bridge domains configured.'

        table_data = [
            {
                'BD-ID': d['bd_id'],
                'Age(min)': 'off' if d['mac_age'] == 0 else d['mac_age'],
                'Learning': 'on' if d['learning'] else 'off',
                'U-Forwrd': 'on' if d['forward'] else 'off',
                'UU-Flood': 'flood' if d['uu_flood'] else 'drop',
                'Flooding': 'on' if d['flood'] else 'off',
                'ARP-Term': 'on' if d['arp_term'] else 'off',
                'arp-ufwd': 'on' if d['arp_ufwd'] else 'off',
                'BVI-Intf': (
                    self.vpp.get_interface_name(d['bvi_interface'])
                    if d['bvi_interface'] != NO_INDEX
                    else 'N/A'
                ),
            }
            for d in data
        ]
        return tabulate(table_data, headers='keys', tablefmt='simple', numalign='left')

    def bridge_domain(self, raw: bool, ifname: typing.Optional[str] = None):
        bd_id = self._parse_bridge_id(ifname)
        data = self._get_bridge_domain_raw(bd_id)
        return data if raw else self._show_bridge_domain_formatted(data)

    def bridge_domain_details(self, raw: bool, ifname: typing.List):
        bd_id = self._parse_bridge_id(ifname)

        # VPP API call is not so informative -> use CLI command
        cmd_command = f'show bridge-domain {bd_id} detail'
        data = self.vpp.cli_cmd(cmd_command)

        if raw:
            return [data.reply]

        return data.reply


# -----------------------------
# VyOS IPFIX op-mode entries
# -----------------------------
def show_ipfix_interfaces(raw: bool):
    return VPPShow().ipfix_interfaces(raw)


def show_ipfix_collectors(raw: bool):
    return VPPShow().ipfix_collectors(raw)


def show_ipfix_table(raw: bool):
    return VPPShow().ipfix_table(raw)


# -----------------------------
# VPP LACP information
# -----------------------------
@_verify('interfaces bonding')
def show_lacp(raw: bool, ifname: typing.Optional[str]):
    return VPPShow().lacp_info(raw, ifname)


@_verify('interfaces bonding')
def show_lacp_details(raw: bool, ifname: typing.Optional[str]):
    return VPPShow().lacp_details(raw, ifname)


# -----------------------------
# Bridge op-mode entries
# -----------------------------
@_verify('interfaces bridge')
def show_bridge(raw: bool, ifname: typing.Optional[str] = None):
    return VPPShow().bridge_domain(raw, ifname)


@_verify('interfaces bridge')
def show_bridge_details(raw: bool, ifname: typing.Optional[str] = None):
    return VPPShow().bridge_domain_details(raw, ifname)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
