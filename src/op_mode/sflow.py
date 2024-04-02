#!/usr/bin/env python3
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
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

import dbus
import sys

from tabulate import tabulate

from vyos.configquery import ConfigTreeQuery

import vyos.opmode


def _get_raw_sflow():
    bus = dbus.SystemBus()
    config = ConfigTreeQuery()

    interfaces = config.values('system sflow interface')
    servers = config.list_nodes('system sflow server')

    sflow = bus.get_object('net.sflow.hsflowd', '/net/sflow/hsflowd')
    sflow_telemetry = dbus.Interface(
        sflow, dbus_interface='net.sflow.hsflowd.telemetry')
    agent_address = sflow_telemetry.GetAgent()
    samples_dropped = int(sflow_telemetry.Get('dropped_samples'))
    packet_drop_sent = int(sflow_telemetry.Get('event_samples'))
    samples_packet_sent = int(sflow_telemetry.Get('flow_samples'))
    samples_counter_sent = int(sflow_telemetry.Get('counter_samples'))
    datagrams_sent = int(sflow_telemetry.Get('datagrams'))
    rtmetric_samples = int(sflow_telemetry.Get('rtmetric_samples'))
    event_samples_suppressed = int(sflow_telemetry.Get('event_samples_suppressed'))
    samples_suppressed = int(sflow_telemetry.Get('flow_samples_suppressed'))
    counter_samples_suppressed = int(
        sflow_telemetry.Get("counter_samples_suppressed"))
    version = sflow_telemetry.GetVersion()

    sflow_dict = {
        'agent_address': agent_address,
        'sflow_interfaces': interfaces,
        'sflow_servers': servers,
        'counter_samples_sent': samples_counter_sent,
        'datagrams_sent': datagrams_sent,
        'packet_drop_sent': packet_drop_sent,
        'packet_samples_dropped': samples_dropped,
        'packet_samples_sent': samples_packet_sent,
        'rtmetric_samples': rtmetric_samples,
        'event_samples_suppressed': event_samples_suppressed,
        'flow_samples_suppressed': samples_suppressed,
        'counter_samples_suppressed': counter_samples_suppressed,
        'hsflowd_version': version
    }
    return sflow_dict


def _get_formatted_sflow(data):
    table = [
        ['Agent address', f'{data.get("agent_address")}'],
        ['sFlow interfaces', f'{data.get("sflow_interfaces", "n/a")}'],
        ['sFlow servers', f'{data.get("sflow_servers", "n/a")}'],
        ['Counter samples sent', f'{data.get("counter_samples_sent")}'],
        ['Datagrams sent', f'{data.get("datagrams_sent")}'],
        ['Packet samples sent', f'{data.get("packet_samples_sent")}'],
        ['Packet samples dropped', f'{data.get("packet_samples_dropped")}'],
        ['Packet drops sent', f'{data.get("packet_drop_sent")}'],
        ['Packet drops suppressed', f'{data.get("event_samples_suppressed")}'],
        ['Flow samples suppressed', f'{data.get("flow_samples_suppressed")}'],
        ['Counter samples suppressed', f'{data.get("counter_samples_suppressed")}']
    ]

    return tabulate(table)


def show(raw: bool):

    config = ConfigTreeQuery()
    if not config.exists('system sflow'):
        raise vyos.opmode.UnconfiguredSubsystem(
            '"system sflow" is not configured!')

    sflow_data = _get_raw_sflow()
    if raw:
        return sflow_data
    else:
        return _get_formatted_sflow(sflow_data)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
