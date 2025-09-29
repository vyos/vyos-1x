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
#

import os
import re
import sys
import glob
import json
import typing
import textwrap
from datetime import datetime
from tabulate import tabulate

import vyos.opmode
from vyos.ifconfig import Section
from vyos.ifconfig import Interface
from vyos.ifconfig import VRRP
from vyos.utils.dict import dict_set_nested
from vyos.utils.network import get_interface_vrf
from vyos.utils.network import interface_exists
from vyos.utils.process import cmd
from vyos.utils.process import rc_cmd
from vyos.utils.process import call
from vyos.configquery import op_mode_config_dict

def catch_broken_pipe(func):
    def wrapped(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except (BrokenPipeError, KeyboardInterrupt):
            # Flush output to /dev/null and bail out.
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno()) # pylint: disable = no-member
    return wrapped

# The original implementation of filtered_interfaces has signature:
# (ifnames: list, iftypes: typing.Union[str, list], vif: bool, vrrp: bool) -> intf: Interface:
# Arg types allowed in CLI (ifnames: str, iftypes: str) were manually
# re-typed from argparse args.
# We include the function in a general form, however op-mode standard
# functions will restrict to the CLI-allowed arg types, wrapped in Optional.
def filtered_interfaces(ifnames: typing.Union[str, list],
                        iftypes: typing.Union[str, list],
                        vif: bool, vrrp: bool) -> Interface:
    """
    get all interfaces from the OS and return them; ifnames can be used to
    filter which interfaces should be considered

    ifnames: a list of interface names to consider, empty do not filter

    return an instance of the Interface class
    """
    if isinstance(ifnames, str):
        ifnames = [ifnames] if ifnames else []
    if isinstance(iftypes, list):
        for iftype in iftypes:
            yield from filtered_interfaces(ifnames, iftype, vif, vrrp)

    for ifname in Section.interfaces(iftypes):
        # Bail out early if interface name not part of our search list
        if ifnames and ifname not in ifnames:
            continue

        # As we are only "reading" from the interface - we must use the
        # generic base class which exposes all the data via a common API
        interface = Interface(ifname, create=False, debug=False)

        # VLAN interfaces have a '.' in their name by convention
        if vif and not '.' in ifname:
            continue

        if vrrp:
            vrrp_interfaces = VRRP.active_interfaces()
            if ifname not in vrrp_interfaces:
                continue

        yield interface

def is_interface_has_mac(interface_name):
    interface_no_mac = ('tun', 'wg')
    return not any(interface_name.startswith(prefix) for prefix in interface_no_mac)

def detailed_output(dataset, headers):
    for data in dataset:
        adjusted_rule = data + [""] * (len(headers) - len(data)) # account for different header length, like default-action
        transformed_rule = [[header, adjusted_rule[i]] for i, header in enumerate(headers) if i < len(adjusted_rule)] # create key-pair list from headers and rules lists; wrap at 100 char

        print(tabulate(transformed_rule, tablefmt="presto"))
        print()

def _split_text(text, used=0):
    """
    take a string and attempt to split it to fit with the width of the screen

    text: the string to split
    used: number of characted already used in the screen
    """
    no_tty = call('tty -s')

    returned = cmd('stty size') if not no_tty else ''
    returned = returned.split()
    if len(returned) == 2:
        _, columns = tuple(int(_) for _ in returned)
    else:
        _, columns = (40, 80)

    desc_len = columns - used

    line = ''
    for word in text.split():
        if len(line) + len(word) < desc_len:
            line = f'{line} {word}'
            continue
        if line:
            yield line[1:]
            line = f' {word}'
        else:
            line = f'{line} {word}'

    yield line[1:]

def _get_counter_val(prev, now):
    """
    attempt to correct a counter if it wrapped, copied from perl

    prev: previous counter
    now:  the current counter
    """
    # This function has to deal with both 32 and 64 bit counters
    if prev == 0:
        return now

    # device is using 64 bit values assume they never wrap
    value = now - prev
    if (now >> 32) != 0:
        return value

    # The counter has rolled.  If the counter has rolled
    # multiple times since the prev value, then this math
    # is meaningless.
    if value < 0:
        value = (4294967296 - prev) + now

    return value

def _pppoe(ifname):
    out = cmd('ps -C pppd -f')
    if ifname in out:
        return 'C'
    if ifname in [_.split('/')[-1] for _ in glob.glob('/etc/ppp/peers/pppoe*')]:
        return 'D'
    return ''

def _find_intf_by_ifname(intf_l: list, name: str):
    for d in intf_l:
        if d['ifname'] == name:
            return d
    return {}

# lifted out of operational.py to separate formatting from data
def _format_stats(stats, indent=4):
    stat_names = {
        'rx': ['bytes', 'packets', 'errors', 'dropped', 'overrun', 'mcast'],
        'tx': ['bytes', 'packets', 'errors', 'dropped', 'carrier', 'collisions'],
    }

    stats_dir = {
        'rx': ['rx_bytes', 'rx_packets', 'rx_errors', 'rx_dropped', 'rx_over_errors', 'multicast'],
        'tx': ['tx_bytes', 'tx_packets', 'tx_errors', 'tx_dropped', 'tx_carrier_errors', 'collisions'],
    }
    tabs = []
    for rtx in list(stats_dir):
        tabs.append([f'{rtx.upper()}:', ] + stat_names[rtx])
        tabs.append(['', ] + [stats[_] for _ in stats_dir[rtx]])

    s = tabulate(
        tabs,
        stralign="right",
        numalign="right",
        tablefmt="plain"
    )

    p = ' '*indent
    return f'{p}' + s.replace('\n', f'\n{p}')

def _get_raw_data(ifname: typing.Optional[str],
                  iftype: typing.Optional[str],
                  vif: bool, vrrp: bool) -> list:
    if ifname is None:
        ifname = ''
    if iftype is None:
        iftype = ''
    ret =[]
    for interface in filtered_interfaces(ifname, iftype, vif, vrrp):
        res_intf = {}
        cache = interface.operational.load_counters()

        out = cmd(f'ip -json addr show {interface.ifname}')
        res_intf_l = json.loads(out)
        res_intf = res_intf_l[0]

        if res_intf['link_type'] == 'tunnel6':
            # Note that 'ip -6 tun show {interface.ifname}' is not json
            # aware, so find in list
            out = cmd('ip -json -6 tun show')
            tunnel = json.loads(out)
            res_intf['tunnel6'] = _find_intf_by_ifname(tunnel,
                                                       interface.ifname)
            if 'ip6_tnl_f_use_orig_tclass' in res_intf['tunnel6']:
                res_intf['tunnel6']['tclass'] = 'inherit'
                del res_intf['tunnel6']['ip6_tnl_f_use_orig_tclass']

        res_intf['counters_last_clear'] = int(cache.get('timestamp', 0))

        res_intf['description'] = interface.get_alias()

        stats = interface.operational.get_stats()
        for k in list(stats):
            stats[k] = _get_counter_val(cache[k], stats[k])

        res_intf['stats'] = stats

        ret.append(res_intf)

    # find pppoe interfaces that are in a transitional/dead state
    if ifname.startswith('pppoe') and not _find_intf_by_ifname(ret, ifname):
        pppoe_intf = {}
        pppoe_intf['unhandled'] = None
        pppoe_intf['ifname'] = ifname
        pppoe_intf['state'] = _pppoe(ifname)
        ret.append(pppoe_intf)

    return ret

def _get_summary_data(ifname: typing.Optional[str],
                      iftype: typing.Optional[str],
                      vif: bool, vrrp: bool) -> list:
    if ifname is None:
        ifname = ''
    if iftype is None:
        iftype = ''
    ret = []

    for interface in filtered_interfaces(ifname, iftype, vif, vrrp):
        res_intf = {}

        res_intf['ifname'] = interface.ifname
        res_intf['oper_state'] = interface.operational.get_state()
        res_intf['admin_state'] = interface.get_admin_state()
        res_intf['addr'] = [_ for _ in interface.get_addr() if not _.startswith('fe80::')]
        res_intf['description'] = interface.get_alias()
        res_intf['mtu'] = interface.get_mtu()
        res_intf['mac'] = interface.get_mac() if is_interface_has_mac(interface.ifname) else 'n/a'
        res_intf['vrf'] = interface.get_vrf()

        ret.append(res_intf)

    # find pppoe interfaces that are in a transitional/dead state
    if ifname.startswith('pppoe') and not _find_intf_by_ifname(ret, ifname):
        pppoe_intf = {}
        pppoe_intf['unhandled'] = None
        pppoe_intf['ifname'] = ifname
        pppoe_intf['state'] = _pppoe(ifname)
        ret.append(pppoe_intf)

    return ret

def _get_counter_data(ifname: typing.Optional[str],
                      iftype: typing.Optional[str],
                      vif: bool, vrrp: bool) -> list:
    if ifname is None:
        ifname = ''
    if iftype is None:
        iftype = ''
    ret = []
    for interface in filtered_interfaces(ifname, iftype, vif, vrrp):
        res_intf = {}

        oper = interface.operational.get_state()

        if oper not in ('up','unknown'):
            continue

        stats = interface.operational.get_stats()
        cache = interface.operational.load_counters()
        res_intf['ifname'] = interface.ifname
        res_intf['rx_packets'] = _get_counter_val(cache['rx_packets'], stats['rx_packets'])
        res_intf['rx_bytes'] = _get_counter_val(cache['rx_bytes'], stats['rx_bytes'])
        res_intf['tx_packets'] = _get_counter_val(cache['tx_packets'], stats['tx_packets'])
        res_intf['tx_bytes'] = _get_counter_val(cache['tx_bytes'], stats['tx_bytes'])
        res_intf['rx_dropped'] = _get_counter_val(cache['rx_dropped'], stats['rx_dropped'])
        res_intf['tx_dropped'] = _get_counter_val(cache['tx_dropped'], stats['tx_dropped'])
        res_intf['rx_over_errors'] = _get_counter_val(cache['rx_over_errors'], stats['rx_over_errors'])
        res_intf['tx_carrier_errors'] = _get_counter_val(cache['tx_carrier_errors'], stats['tx_carrier_errors'])

        ret.append(res_intf)

    return ret

def _get_kernel_data(raw, ifname = None, detail = False,
                     statistics = False):
    if ifname:
        # Check if the interface exists
        if not interface_exists(ifname):
            raise vyos.opmode.IncorrectValue(f"{ifname} does not exist!")
        int_name = f'dev {ifname}'
    else:
        int_name = ''

    kernel_interface = json.loads(cmd(f'ip -j -d -s address show {int_name}'))

    # Return early if raw
    if raw:
        return kernel_interface, None

    # Format the kernel data
    kernel_interface_out = _format_kernel_data(kernel_interface, detail, statistics)

    return kernel_interface, kernel_interface_out

def _format_kernel_data(data, detail, statistics):
    output_list = []
    podman_vrf = {}
    tmpInfo = {}

    # Sort interfaces by name
    for interface in sorted(data, key=lambda x: x.get('ifname', '')):
        interface_name = interface.get('ifname', '')

        # Skip VRF interfaces
        if interface.get('linkinfo', {}).get('info_kind') == 'vrf':
            continue
        # Skip spawned interfaces
        elif interface_name.startswith(('tunl', 'gre', 'erspan', 'pim6reg')):
            continue

        master = interface.get('master', 'default')
        vrf = get_interface_vrf(interface)

        # Get the device model; ex. Intel Corporation Ethernet Controller I225-V
        dev_model = interface.get('parentdev', '')
        if 'parentdev' in interface:
            parentdev = interface['parentdev']
            if re.match(r'^[0-9a-fA-F]{4}:', parentdev):
                dev_model = cmd(f'lspci -nn -s {parentdev}').split(']:')[1].strip()

        # Get the IP addresses on interface
        ip_list = []
        has_global = False

        for ip in interface['addr_info']:
            if ip.get('scope') in ('global', 'host'):
                has_global = True
                local = ip.get('local', '-')
                prefixlen = ip.get('prefixlen', '')
                ip_list.append(f"{local}/{prefixlen}")

        # If no global IP address, add '-'; indicates no IP address on interface
        if not has_global:
            ip_list.append('-')

        # Generate a mapping of podman interfaces to their VRF
        if interface_name.startswith('pod-'):
            dict_set_nested(f'{interface_name}.vrf', master, podman_vrf)

        # If the veth interface's master is a podman interface, the VRF is the VRF of the podman interface
        if master.startswith('pod-'):
            vrf = podman_vrf.get(master).get('vrf', 'default')

        rx_stats = interface.get('stats64', {}).get('rx')
        tx_stats = interface.get('stats64', {}).get('tx')

        sl_status = ('A' if not 'UP' in interface['flags'] else 'u') + '/' + ('D' if interface['operstate'] == 'DOWN' else 'u')

        # Generate temporary dict to hold data
        tmpInfo['ifname'] = interface_name
        tmpInfo['ip'] = ip_list
        tmpInfo['mac'] = interface.get('address', 'n/a') if is_interface_has_mac(interface_name) else 'n/a'
        tmpInfo['mtu'] = interface.get('mtu', '')
        tmpInfo['vrf'] = vrf
        tmpInfo['status'] = sl_status
        tmpInfo['description'] = "\n".join(textwrap.wrap(interface.get('ifalias', ''), width=50))
        tmpInfo['device'] = dev_model
        tmpInfo['alternate_names'] = interface.get('altnames', '')
        tmpInfo['minimum_mtu'] = interface.get('min_mtu', '')
        tmpInfo['maximum_mtu'] = interface.get('max_mtu', '')
        tmpInfo['rx_packets'] = rx_stats.get('packets', "")
        tmpInfo['rx_bytes'] = rx_stats.get('bytes', "")
        tmpInfo['rx_errors'] = rx_stats.get('errors', "")
        tmpInfo['rx_dropped'] = rx_stats.get('dropped', "")
        tmpInfo['rx_over_errors'] = rx_stats.get('over_errors', '')
        tmpInfo['multicast'] = rx_stats.get('multicast', "")
        tmpInfo['tx_packets'] = tx_stats.get('packets', "")
        tmpInfo['tx_bytes'] = tx_stats.get('bytes', "")
        tmpInfo['tx_errors'] = tx_stats.get('errors', "")
        tmpInfo['tx_dropped'] = tx_stats.get('dropped', "")
        tmpInfo['tx_carrier_errors'] = tx_stats.get('carrier_errors', "")
        tmpInfo['tx_collisions'] = tx_stats.get('collisions', "")

        # Order the stats based on 'detail' or 'statistics'
        if detail:
            stat_keys = [
                "rx_packets", "rx_bytes", "rx_errors", "rx_dropped",
                "rx_over_errors", "multicast",
                "tx_packets", "tx_bytes", "tx_errors", "tx_dropped",
                "tx_carrier_errors", "tx_collisions",
            ]
        elif statistics:
            stat_keys = [
                "rx_packets", "rx_bytes", "tx_packets", "tx_bytes",
                "rx_dropped", "tx_dropped", "rx_errors", "tx_errors",
            ]
        else:
            stat_keys = []

        stat_list = [tmpInfo.get(k, "") for k in stat_keys]

        # Generate output list; detail adds more fields
        output_list.append([tmpInfo['ifname'],
                            *(['\n'.join(tmpInfo['ip'])] if not statistics else []),
                            *([tmpInfo['mac']] if not statistics else []),
                            *([tmpInfo['vrf']] if not statistics else []),
                            *([tmpInfo['mtu']] if not statistics else []),
                            *([tmpInfo['status']] if not statistics else []),
                            *([tmpInfo['description']] if not statistics else []),
                            *([tmpInfo['device']] if detail else []),
                            *(['\n'.join(tmpInfo['alternate_names'])] if detail else []),
                            *([tmpInfo['minimum_mtu']] if detail else []),
                            *([tmpInfo['maximum_mtu']] if detail else []),
                            *(stat_list if any([detail, statistics]) else [])])

    return output_list

@catch_broken_pipe
def _format_show_data(data: list):
    unhandled = []
    for intf in data:
        if 'unhandled' in intf:
            unhandled.append(intf)
            continue
        # instead of reformatting data, call non-json output:
        rc, out = rc_cmd(f"ip addr show {intf['ifname']}")
        if rc != 0:
            continue
        out = re.sub('^\d+:\s+','',out)
        # add additional data already collected
        if 'tunnel6' in intf:
            t6_d = intf['tunnel6']
            t6_str = 'encaplimit %s hoplimit %s tclass %s flowlabel %s (flowinfo %s)' % (
                    t6_d.get('encap_limit', ''), t6_d.get('hoplimit', ''),
                    t6_d.get('tclass', ''), t6_d.get('flowlabel', ''),
                    t6_d.get('flowinfo', ''))
            out = re.sub('(\n\s+)(link/tunnel6)', f'\g<1>{t6_str}\g<1>\g<2>', out)
        print(out)
        ts = intf.get('counters_last_clear', 0)
        if ts:
            when = datetime.fromtimestamp(ts).strftime("%a %b %d %R:%S %Z %Y")
            print(f'    Last clear: {when}')
        description = intf.get('description', '')
        if description:
            print(f'    Description: {description}')

        stats = intf.get('stats', {})
        if stats:
            print()
            print(_format_stats(stats))

    for intf in unhandled:
        string = {
            'C': 'Coming up',
            'D': 'Link down'
        }[intf['state']]
        print(f"{intf['ifname']}: {string}")

    return 0

@catch_broken_pipe
def _format_show_summary(data):
    format1 = '%-16s %-33s %-4s %s'
    format2 = '%-16s %s'

    print('Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down')
    print(format1 % ("Interface", "IP Address", "S/L", "Description"))
    print(format1 % ("---------", "----------", "---", "-----------"))

    unhandled = []
    for intf in data:
        if 'unhandled' in intf:
            unhandled.append(intf)
            continue
        ifname = [intf['ifname'],]
        oper = ['u',] if intf['oper_state'] in ('up', 'unknown') else ['D',]
        admin = ['u',] if intf['admin_state'] in ('up', 'unknown') else ['A',]
        addrs = intf['addr'] or ['-',]
        descs = list(_split_text(intf['description'], 0))

        while ifname or oper or admin or addrs or descs:
            i = ifname.pop(0) if ifname else ''
            a = addrs.pop(0) if addrs else ''
            d = descs.pop(0) if descs else ''
            s = [admin.pop(0)] if admin else []
            l = [oper.pop(0)] if oper else []
            if len(a) < 33:
                print(format1 % (i, a, '/'.join(s+l), d))
            else:
                print(format2 % (i, a))
                print(format1 % ('', '', '/'.join(s+l), d))

    for intf in unhandled:
        string = {
            'C': 'u/D',
            'D': 'A/D'
        }[intf['state']]
        print(format1 % (ifname, '', string, ''))

    return 0

@catch_broken_pipe
def _format_show_summary_extended(data):
    headers = ["Interface", "IP Address", "MAC", "VRF", "MTU", "S/L", "Description"]
    table_data = []

    print('Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down')

    for intf in data:
        if 'unhandled' in intf:
            continue

        ifname = intf['ifname']
        oper_state = 'u' if intf['oper_state'] in ('up', 'unknown') else 'D'
        admin_state = 'u' if intf['admin_state'] in ('up', 'unknown') else 'A'
        addrs = intf['addr'] or ['-']
        description = '\n'.join(_split_text(intf['description'], 0))
        mac = intf['mac'] if intf['mac'] else 'n/a'
        mtu = intf['mtu'] if intf['mtu'] else 'n/a'
        vrf = intf['vrf'] if intf['vrf'] else 'default'

        ip_addresses = '\n'.join(ip for ip in addrs)

        # Create a row for the table
        row = [
            ifname,
            ip_addresses,
            mac,
            vrf,
            mtu,
            f"{admin_state}/{oper_state}",
            description,
        ]

        # Append the row to the table data
        table_data.append(row)

    for intf in data:
        if 'unhandled' in intf:
            string = {'C': 'u/D', 'D': 'A/D'}[intf['state']]
            table_data.append([intf['ifname'], '', '', '', '', string, ''])

    print(tabulate(table_data, headers))

    return 0

@catch_broken_pipe
def _format_show_counters(data: list):
    data_entries = []
    for entry in data:
            interface = entry.get('ifname')
            rx_packets = entry.get('rx_packets')
            rx_bytes = entry.get('rx_bytes')
            tx_packets = entry.get('tx_packets')
            tx_bytes = entry.get('tx_bytes')
            rx_dropped = entry.get('rx_dropped')
            tx_dropped = entry.get('tx_dropped')
            rx_errors = entry.get('rx_over_errors')
            tx_errors = entry.get('tx_carrier_errors')
            data_entries.append([interface, rx_packets, rx_bytes, tx_packets, tx_bytes, rx_dropped, tx_dropped, rx_errors, tx_errors])

    headers = ['Interface', 'Rx Packets', 'Rx Bytes', 'Tx Packets', 'Tx Bytes', 'Rx Dropped', 'Tx Dropped', 'Rx Errors', 'Tx Errors']
    output = tabulate(data_entries, headers, numalign="left")
    print (output)
    return output

def show_kernel(raw: bool, intf_name: typing.Optional[str],
                detail: bool, statistics: bool):
    raw_data, data = _get_kernel_data(raw, intf_name, detail, statistics)

    # Return early if raw
    if raw:
        return raw_data

    if detail:
        # Detail headers; ex. show interfaces kernel detail; show interfaces kernel eth0 detail
        detail_header = ['Interface', 'IP Address', 'MAC', 'VRF', 'MTU', 'S/L', 'Description',
                        'Device', 'Alternate Names','Minimum MTU', 'Maximum MTU', 'RX_Packets',
                        'RX_Bytes', 'RX_Errors', 'RX_Dropped', 'Receive Overrun Errors', 'Received Multicast',
                        'TX_Packets', 'TX_Bytes', 'TX_Errors', 'TX_Dropped', 'Transmit Carrier Errors',
                        'Transmit Collisions']
    elif statistics:
        # Statistics headers; ex. show interfaces kernel statistics; show interfaces kernel eth0 statistics
        headers = ['Interface', 'Rx Packets', 'Rx Bytes', 'Tx Packets', 'Tx Bytes', 'Rx Dropped', 'Tx Dropped', 'Rx Errors', 'Tx Errors']
    else:
        # Normal headers; ex. show interfaces kernel; show interfaces kernel eth0
        print('Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down')
        headers = ['Interface', 'IP Address', 'MAC', 'VRF', 'MTU', 'S/L', 'Description']


    if detail:
        detailed_output(data, detail_header)
    else:
        print(tabulate(data, headers))

def _show_raw(data: list, intf_name: str):
    if intf_name is not None and len(data) <= 1:
        try:
            return data[0]
        except IndexError:
            raise vyos.opmode.UnconfiguredObject(
                f"Interface {intf_name} does not exist")
    else:
        return data


def show(raw: bool, intf_name: typing.Optional[str],
                    intf_type: typing.Optional[str],
                    vif: bool, vrrp: bool):
    data = _get_raw_data(intf_name, intf_type, vif, vrrp)
    if raw:
        return _show_raw(data, intf_name)
    return _format_show_data(data)

def show_summary(raw: bool, intf_name: typing.Optional[str],
                            intf_type: typing.Optional[str],
                            vif: bool, vrrp: bool):
    data = _get_summary_data(intf_name, intf_type, vif, vrrp)
    if raw:
        return _show_raw(data, intf_name)
    return _format_show_summary(data)

def show_summary_extended(raw: bool, intf_name: typing.Optional[str],
                            intf_type: typing.Optional[str],
                            vif: bool, vrrp: bool):
    data = _get_summary_data(intf_name, intf_type, vif, vrrp)
    if raw:
        return _show_raw(data, intf_name)
    return _format_show_summary_extended(data)

def show_counters(raw: bool, intf_name: typing.Optional[str],
                             intf_type: typing.Optional[str],
                             vif: bool, vrrp: bool):
    data = _get_counter_data(intf_name, intf_type, vif, vrrp)
    if raw:
        return _show_raw(data, intf_name)
    return _format_show_counters(data)

def show_vlan_to_vni(raw: bool, intf_name: typing.Optional[str],
                     vid: typing.Optional[str], detail: bool,
                     statistics: bool):
    if not interface_exists(intf_name):
        raise vyos.opmode.UnconfiguredObject(f"Interface {intf_name} does not exist\n")

    if not vid:
        vid = "all"

    tunnel_data = json.loads(cmd(f"bridge -j vlan tunnelshow dev {intf_name} vid {vid}"))

    if not tunnel_data:
        if vid == "all":
            raise vyos.opmode.UnconfiguredObject(f"No VLAN-to-VNI mapping found for interface {intf_name}\n")
        else:
            raise vyos.opmode.UnconfiguredObject(f"No VLAN-to-VNI mapping found for VLAN {vid}\n")

    statistics_data = json.loads(cmd(f"bridge -j -s vlan tunnelshow dev {intf_name} vid {vid}"))[0]

    mapping_config = op_mode_config_dict(['interfaces', 'vxlan', intf_name, 'vlan-to-vni'],
                        get_first_key=True)

    raw_data = {intf_name: {}}
    output_list = []

    for tunnel in tunnel_data[0].get("tunnels", []):
        tunnel_id = tunnel.get("tunid")
        tunnel_dict = raw_data[intf_name][tunnel_id] = {}

        for vlan in statistics_data.get("vlans", []):
            if vlan.get("vid") == tunnel.get("vlan"):
                vlan_id = str(vlan.get("vid"))
                description = mapping_config.get(vlan_id, {}).get("description", "")

                # detail allows for longer descriptions; each output wraps to 80 characters
                if detail:
                    description = "\n".join(textwrap.wrap(description, width=65))
                elif raw:
                    pass
                else:
                    description = "\n".join(textwrap.wrap(description, width=48))

                if raw:
                    tunnel_dict["vlan"] = vlan_id
                    tunnel_dict["rx_bytes"] = vlan.get("rx_bytes")
                    tunnel_dict["tx_bytes"] = vlan.get("tx_bytes")
                    tunnel_dict["rx_packets"] = vlan.get("rx_packets")
                    tunnel_dict["tx_packets"] = vlan.get("tx_packets")
                    tunnel_dict["description"] = description
                else:
                    #Generate output list; detail adds more fields
                    output_list.append([
                        *([intf_name] if not detail else []),
                        vlan_id,
                        tunnel_id,
                        *([description] if not statistics else []),
                        *([vlan.get("rx_packets")] if any([detail, statistics]) else []),
                        *([vlan.get("rx_bytes")] if any([detail, statistics]) else []),
                        *([vlan.get("tx_packets")] if any([detail, statistics]) else []),
                        *([vlan.get("tx_bytes")] if any([detail, statistics]) else [])
                    ])

    if raw:
        return raw_data

    if detail:
        # Detail headers; ex. show interfaces vxlan vxlan1 vlan-to-vni detail
        detail_header = ['VLAN', 'VNI', 'Description', 'Rx Packets', 'Rx Bytes', 'Tx Packets', 'Tx Bytes']
        print('-' * 35)
        print(f"Interface: {intf_name}\n")
        detailed_output(output_list, detail_header)
    elif statistics:
        # Statistics headers; ex. show interfaces vxlan vxlan1 vlan-to-vni statistics
        headers = ['Interface', 'VLAN', 'VNI', 'Rx Packets', 'Rx Bytes', 'Tx Packets', 'Tx Bytes']
        print(tabulate(output_list, headers))
    else:
        # Normal headers; ex. show interfaces vxlan vxlan1 vlan-to-vni
        headers = ['Interface', 'VLAN', 'VNI', 'Description']
        print(tabulate(output_list, headers))

def clear_counters(intf_name: typing.Optional[str],
                   intf_type: typing.Optional[str],
                   vif: bool, vrrp: bool):
    for interface in filtered_interfaces(intf_name, intf_type, vif, vrrp):
        interface.operational.clear_counters()

def reset_counters(intf_name: typing.Optional[str],
                   intf_type: typing.Optional[str],
                   vif: bool, vrrp: bool):
    for interface in filtered_interfaces(intf_name, intf_type, vif, vrrp):
        interface.operational.reset_counters()

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
