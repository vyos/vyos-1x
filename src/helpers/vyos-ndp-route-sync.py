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

import argparse
import atexit
import json
import select
import signal
import socket
import struct
import time

from dataclasses import dataclass
from ipaddress import IPv6Address, IPv6Network
from pathlib import Path

from vyos import airbag
from vyos.utils.process import rc_cmd

try:
    from pyroute2.iproute import IPRoute
    from pyroute2.netlink import rtnl
    from pyroute2.netlink.rtnl import ndmsg
except ImportError:
    IPRoute = None
    rtnl = None
    ndmsg = None

airbag.enable()


default_config = Path('/run/ndppd/route-sync.conf')
default_proto = 'ndp-proxy-sync'
default_interval = 2
default_hold_time = 120
fast_sync_delay = 0.2
max_packets_per_socket = 128
max_learned_routes = 4096
invalid_states = {'FAILED', 'INCOMPLETE', 'NONE'}
usable_states = {'REACHABLE', 'STALE', 'DELAY', 'PROBE', 'PERMANENT', 'NOARP'}
eth_p_all = 0x0003
eth_p_ipv6 = 0x86DD
vlan_ethertypes = {0x8100, 0x88A8, 0x9100}
icmpv6_next_header = 58
nd_neighbor_solicit = 135
nd_neighbor_advert = 136
packet_outgoing = getattr(socket, 'PACKET_OUTGOING', 4)
packet_auxdata = getattr(socket, 'PACKET_AUXDATA', 8)
sol_packet = getattr(socket, 'SOL_PACKET', 263)
is_running = True

if ndmsg:
    invalid_state_mask = ndmsg.NUD_INCOMPLETE | ndmsg.NUD_FAILED
    usable_state_mask = (
        ndmsg.NUD_REACHABLE
        | ndmsg.NUD_STALE
        | ndmsg.NUD_DELAY
        | ndmsg.NUD_PROBE
        | ndmsg.NUD_PERMANENT
        | ndmsg.NUD_NOARP
    )
else:
    invalid_state_mask = 0
    usable_state_mask = 0


@dataclass(frozen=True)
class Rule:
    prefix: IPv6Network
    interface: str


@dataclass(frozen=True)
class LearnedRoute:
    interface: str
    expires_at: float


def normalize_states(states):
    if not states:
        return set()
    if isinstance(states, str):
        states = [states]
    return {state.upper() for state in states}


def normalize_mac(address):
    if not isinstance(address, str):
        return None

    parts = address.split(':')
    if len(parts) != 6:
        return None

    octets = []
    for part in parts:
        if not part:
            return None
        try:
            value = int(part, 16)
        except ValueError:
            return None
        if value < 0 or value > 255:
            return None
        octets.append(f'{value:02x}')

    return ':'.join(octets)


def neighbor_is_usable(neighbor):
    states = normalize_states(neighbor.get('state'))
    if not states or states.intersection(invalid_states):
        return False
    return bool(states.intersection(usable_states))


def neighbor_state_is_usable_rtnl(state):
    if not isinstance(state, int) or state == 0:
        return False
    if state & invalid_state_mask:
        return False
    return bool(state & usable_state_mask)


def cleanup_routes(proto):
    routes = get_managed_routes(proto)
    for destination, interface in routes.items():
        rc_cmd(f'ip -6 route del {destination}/128 dev {interface} proto {proto}')


def get_managed_routes(proto):
    rc, data = rc_cmd(f'ip --json -6 route show proto {proto}')
    if rc != 0 or not data:
        return {}

    try:
        routes = json.loads(data)
    except json.JSONDecodeError:
        return {}

    managed = {}
    for route in routes:
        destination = route.get('dst')
        interface = route.get('dev')
        if not destination or not interface:
            continue

        try:
            address, plen = destination.split('/')
        except ValueError:
            continue

        if plen != '128':
            continue

        try:
            destination = IPv6Address(address).compressed
        except ValueError:
            continue

        managed[destination] = interface

    return managed


def get_neighbors(interface):
    rc, data = rc_cmd(f'ip --json -6 neigh show dev {interface}')
    if rc != 0 or not data:
        return set(), set(), set()

    try:
        neighbors = json.loads(data)
    except json.JSONDecodeError:
        return set(), set(), set()

    addresses = set()
    sources = set()
    macs = set()
    for neighbor in neighbors:
        if not neighbor_is_usable(neighbor):
            continue

        lladdr = normalize_mac(neighbor.get('lladdr'))
        if lladdr:
            macs.add(lladdr)

        destination = neighbor.get('dst')
        if not destination:
            continue

        try:
            source = IPv6Address(destination)
        except ValueError:
            continue

        if not should_track_neighbor_source(source):
            continue

        sources.add(source)
        if should_learn_address(source):
            addresses.add(source)

    return addresses, sources, macs


def sync_routes(proto, desired):
    current = get_managed_routes(proto)

    for destination, interface in desired.items():
        if current.get(destination) == interface:
            continue
        rc_cmd(f'ip -6 route replace {destination}/128 dev {interface} proto {proto}')

    for destination, interface in current.items():
        if destination in desired:
            continue
        rc_cmd(f'ip -6 route del {destination}/128 dev {interface} proto {proto}')


def load_config(config_path):
    config_file = Path(config_path)
    if not config_file.exists():
        return default_proto, default_interval, default_hold_time, []

    try:
        config = json.loads(config_file.read_text())
    except json.JSONDecodeError:
        return default_proto, default_interval, default_hold_time, []

    proto = config.get('proto', default_proto)
    interval = config.get('interval', default_interval)
    if not isinstance(interval, int) or interval < 1:
        interval = default_interval
    hold_time = config.get('hold_time', default_hold_time)
    if not isinstance(hold_time, int) or hold_time < interval:
        hold_time = max(default_hold_time, interval)

    rules = []
    for rule in config.get('rules', []):
        interface = rule.get('interface')
        prefix = rule.get('prefix')
        if not interface or not prefix:
            continue

        try:
            network = IPv6Network(prefix, strict=False)
        except ValueError:
            continue

        rules.append(Rule(prefix=network, interface=interface))

    return proto, interval, hold_time, rules


def should_learn_address(address):
    if address.is_multicast:
        return False
    if address.is_link_local:
        return False
    if address.is_unspecified or address.is_loopback:
        return False
    return True


def get_rule_map(rules):
    rule_map = {}
    for rule in sorted(rules, key=lambda item: item.prefix.prefixlen, reverse=True):
        if rule.interface not in rule_map:
            rule_map[rule.interface] = []
        rule_map[rule.interface].append(rule.prefix)
    return rule_map


def learn_address(learned, interface, address, rule_map, hold_time):
    if not should_learn_address(address):
        return False
    if interface not in rule_map:
        return False

    for prefix in rule_map[interface]:
        if address in prefix:
            destination = address.compressed
            now = time.monotonic()
            entry = LearnedRoute(interface=interface, expires_at=now + hold_time)
            current = learned.get(destination)

            if current and current.interface == interface:
                learned[destination] = entry
                return False

            if current:
                learned[destination] = entry
                return True

            if len(learned) >= max_learned_routes:
                prune_learned_routes(learned)
                if len(learned) >= max_learned_routes:
                    return False

            learned[destination] = entry
            return True

    return False


def unlearn_address(learned, interface, address):
    destination = address.compressed
    current = learned.get(destination)
    if not current:
        return False
    if current.interface != interface:
        return False
    del learned[destination]
    return True


def get_neighbor_map(rule_map):
    neighbor_map = {}
    for interface in rule_map:
        addresses, sources, macs = get_neighbors(interface)
        neighbor_map[interface] = {'addresses': addresses, 'sources': sources, 'macs': macs}
    return neighbor_map


def seed_from_neighbors(learned, rule_map, hold_time, neighbor_map=None):
    if neighbor_map is None:
        neighbor_map = get_neighbor_map(rule_map)

    learned_new = False
    for interface, neighbors in neighbor_map.items():
        for address in neighbors['addresses']:
            if learn_address(learned, interface, address, rule_map, hold_time):
                learned_new = True
    return learned_new


def open_packet_socket(interface):
    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(eth_p_all))
    sock.bind((interface, 0))
    sock.setblocking(False)
    try:
        sock.setsockopt(sol_packet, packet_auxdata, 1)
    except OSError:
        pass
    return sock


def parse_nd_target(packet, aux_vlan_id=None):
    if len(packet) < 14:
        return None, None, None, False, None

    offset = 14
    vlan_tagged = False
    vlan_id = None
    source_mac = normalize_mac(':'.join(f'{octet:02x}' for octet in packet[6:12]))
    ethertype = int.from_bytes(packet[12:14], 'big')
    while ethertype in vlan_ethertypes:
        vlan_tagged = True
        if len(packet) < offset + 4:
            return None, None, source_mac, vlan_tagged, vlan_id
        if vlan_id is None:
            tci = int.from_bytes(packet[offset:offset + 2], 'big')
            vlan_id = tci & 0x0FFF
        ethertype = int.from_bytes(packet[offset + 2:offset + 4], 'big')
        offset += 4

    if ethertype != eth_p_ipv6 or len(packet) < offset + 40:
        return None, None, source_mac, vlan_tagged, vlan_id

    try:
        source = IPv6Address(packet[offset + 8:offset + 24])
    except ValueError:
        source = None

    if packet[offset + 6] != icmpv6_next_header:
        return None, source, source_mac, vlan_tagged, vlan_id

    icmp_offset = offset + 40
    if len(packet) < icmp_offset + 24:
        return None, source, source_mac, vlan_tagged, vlan_id

    icmp_type = packet[icmp_offset]
    if icmp_type not in (nd_neighbor_solicit, nd_neighbor_advert):
        return None, source, source_mac, vlan_tagged, vlan_id

    try:
        target = IPv6Address(packet[icmp_offset + 8:icmp_offset + 24])
    except ValueError:
        return None, source, source_mac, vlan_tagged, vlan_id

    if aux_vlan_id is not None:
        vlan_tagged = True
        if vlan_id is None:
            vlan_id = aux_vlan_id

    return target, source, source_mac, vlan_tagged, vlan_id


def get_interface_vlan_id(interface):
    if '.' not in interface:
        return None
    suffix = interface.rsplit('.', 1)[1]
    if not suffix.isdigit():
        return None
    vlan_id = int(suffix)
    if 0 <= vlan_id <= 4094:
        return vlan_id
    return None


def get_interface_parent(interface):
    if '.' not in interface:
        return interface
    return interface.rsplit('.', 1)[0]


def parse_aux_vlan_id(ancdata):
    for cmsg_level, cmsg_type, cmsg_data in ancdata:
        if cmsg_level != sol_packet or cmsg_type != packet_auxdata:
            continue
        if len(cmsg_data) < 20:
            continue

        _, _, _, _, _, tp_vlan_tci, tp_vlan_tpid = struct.unpack('IIIHHHH', cmsg_data[:20])
        if tp_vlan_tpid in vlan_ethertypes:
            return tp_vlan_tci & 0x0FFF

    return None


def collect_nd_targets(sockets, timeout):
    if not sockets:
        time.sleep(timeout)
        return []

    reverse = {sock.fileno(): interface for interface, sock in sockets.items()}
    try:
        ready, _, _ = select.select(list(sockets.values()), [], [], timeout)
    except (ValueError, OSError):
        return []

    learned = []
    for sock in ready:
        interface = reverse.get(sock.fileno())
        if not interface:
            continue

        for _ in range(max_packets_per_socket):
            try:
                packet, ancdata, _, source_info = sock.recvmsg(65535, 256)
            except BlockingIOError:
                break
            except OSError:
                break

            if isinstance(source_info, tuple) and len(source_info) >= 3:
                if source_info[2] == packet_outgoing:
                    continue

            aux_vlan_id = parse_aux_vlan_id(ancdata)
            target, source, source_mac, vlan_tagged, vlan_id = parse_nd_target(packet, aux_vlan_id=aux_vlan_id)
            if not target:
                continue

            rx_interface = None
            if isinstance(source_info, tuple) and source_info:
                rx_interface = source_info[0]

            learned.append((interface, target, source, source_mac, vlan_tagged, vlan_id, rx_interface))

    return learned


def get_sockets(rule_map):
    sockets = {}
    for interface in rule_map:
        try:
            sockets[interface] = open_packet_socket(interface)
        except OSError:
            continue
    return sockets


def close_sockets(sockets):
    for sock in sockets.values():
        try:
            sock.close()
        except OSError:
            continue


def get_desired_routes(learned):
    return {destination: data.interface for destination, data in learned.items()}


def matches_neighbor_cache(target, source, source_mac, neighbors):
    if target in neighbors['addresses']:
        return True
    if source and source in neighbors['sources']:
        return True
    if source_mac and source_mac in neighbors['macs']:
        return True
    return False


def should_track_neighbor_source(address):
    if address.is_multicast:
        return False
    if address.is_unspecified or address.is_loopback:
        return False
    return True


def prune_learned_routes(learned):
    now = time.monotonic()
    changed = False
    for destination in list(learned):
        if learned[destination].expires_at <= now:
            del learned[destination]
            changed = True
    return changed


def open_iproute():
    if IPRoute is None:
        return None
    try:
        iproute = IPRoute(async_qsize=4096)
        iproute.bind(async_cache=True)
        return iproute
    except Exception:
        return None


def close_iproute(iproute):
    if not iproute:
        return
    try:
        iproute.close()
    except Exception:
        pass


def close_iproute_ctx(ctx):
    close_iproute(ctx.get('handle'))


def get_ifindex_map(iproute, rule_map):
    mapping = {}
    if not iproute:
        return mapping

    for interface in rule_map:
        try:
            indices = iproute.link_lookup(ifname=interface)
        except Exception:
            continue
        if not indices:
            continue
        mapping[indices[0]] = interface

    return mapping


def get_netlink_attr(msg, name):
    try:
        value = msg.get_attr(name)
        if value is not None:
            return value
    except Exception:
        pass

    attrs = msg.get('attrs', [])
    for attr_name, attr_value in attrs:
        if attr_name == name:
            return attr_value

    return None


def collect_neighbor_events(iproute, ifindex_map, timeout):
    if not iproute or not rtnl:
        return [], False

    try:
        ready, _, _ = select.select([iproute.fileno()], [], [], timeout)
    except (ValueError, OSError):
        return [], False

    if not ready:
        return [], True

    try:
        messages = iproute.get()
    except Exception:
        return [], False

    events = []
    for msg in messages:
        msg_type = msg.get('header', {}).get('type')
        if msg_type not in (rtnl.RTM_NEWNEIGH, rtnl.RTM_DELNEIGH):
            continue

        if msg.get('family') != socket.AF_INET6:
            continue

        interface = ifindex_map.get(msg.get('ifindex'))
        if not interface:
            continue

        destination = get_netlink_attr(msg, 'NDA_DST')
        if not destination:
            continue

        try:
            address = IPv6Address(destination)
        except ValueError:
            continue

        if not should_learn_address(address):
            continue

        if msg_type == rtnl.RTM_DELNEIGH:
            events.append(('del', interface, address))
            continue

        if neighbor_state_is_usable_rtnl(msg.get('state', 0)):
            events.append(('add', interface, address))

    return events, True


def shutdown(*_):
    global is_running
    is_running = False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=default_config)
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()

    proto, interval, hold_time, rules = load_config(args.config)

    if args.cleanup:
        cleanup_routes(proto)
        return

    if not rules:
        cleanup_routes(proto)
        return

    rule_map = get_rule_map(rules)
    learned_routes = {}
    neighbor_map = get_neighbor_map(rule_map)
    seed_from_neighbors(learned_routes, rule_map, hold_time, neighbor_map=neighbor_map)
    sockets = get_sockets(rule_map)

    iproute = open_iproute()
    iproute_ctx = {'handle': iproute}
    ifindex_map = get_ifindex_map(iproute, rule_map)

    atexit.register(cleanup_routes, proto)
    atexit.register(close_sockets, sockets)
    atexit.register(close_iproute_ctx, iproute_ctx)
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    sync_routes(proto, get_desired_routes(learned_routes))
    last_sync = time.monotonic()
    last_neighbor_refresh = last_sync
    last_netlink_retry = last_sync
    dirty_since = None

    while is_running:
        now = time.monotonic()
        next_sync = last_sync + interval
        next_neighbor_refresh = last_neighbor_refresh + interval
        next_wakeup = min(next_sync, next_neighbor_refresh)
        if dirty_since is not None:
            next_wakeup = min(next_wakeup, dirty_since + fast_sync_delay)
        timeout = max(0, next_wakeup - now)

        for interface, address, source, source_mac, vlan_tagged, vlan_id, rx_interface in collect_nd_targets(sockets, timeout):
            interface_vlan_id = get_interface_vlan_id(interface)
            if interface_vlan_id is None and vlan_tagged:
                continue
            if interface_vlan_id is not None and vlan_tagged and vlan_id != interface_vlan_id:
                continue

            if not rx_interface:
                continue
            if rx_interface != interface:
                interface_parent = get_interface_parent(interface)
                if not (rx_interface == interface_parent and interface_vlan_id is not None):
                    continue

            if learn_address(learned_routes, interface, address, rule_map, hold_time):
                if dirty_since is None:
                    dirty_since = time.monotonic()

        events, netlink_ok = collect_neighbor_events(iproute, ifindex_map, 0)
        if iproute and not netlink_ok:
            close_iproute(iproute)
            iproute = None
            iproute_ctx['handle'] = None
            ifindex_map = {}
            last_netlink_retry = time.monotonic()

        for action, interface, address in events:
            changed = False
            if action == 'add':
                changed = learn_address(learned_routes, interface, address, rule_map, hold_time)
            elif action == 'del':
                changed = unlearn_address(learned_routes, interface, address)

            if changed and dirty_since is None:
                dirty_since = time.monotonic()

        now = time.monotonic()
        if now - last_neighbor_refresh >= interval:
            neighbor_map = get_neighbor_map(rule_map)
            if seed_from_neighbors(learned_routes, rule_map, hold_time, neighbor_map=neighbor_map):
                if dirty_since is None:
                    dirty_since = now

            if iproute:
                ifindex_map = get_ifindex_map(iproute, rule_map)
            elif now - last_netlink_retry >= interval:
                iproute = open_iproute()
                iproute_ctx['handle'] = iproute
                ifindex_map = get_ifindex_map(iproute, rule_map)
                last_netlink_retry = now

            last_neighbor_refresh = now

        if prune_learned_routes(learned_routes):
            if dirty_since is None:
                dirty_since = now

        periodic_due = now - last_sync >= interval
        dirty_due = dirty_since is not None and now - dirty_since >= fast_sync_delay
        if periodic_due or dirty_due:
            sync_routes(proto, get_desired_routes(learned_routes))
            last_sync = now
            dirty_since = None


if __name__ == '__main__':
    main()
