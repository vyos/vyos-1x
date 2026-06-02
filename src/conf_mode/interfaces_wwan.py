#!/usr/bin/env python3
# Copyright (C) 2024-2026 Perle Systems Limited
# SPDX-License-Identifier: GPL-2.0-or-later
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
# interfaces_wwan.py — VyOS conf_mode script for enhanced WWAN interface.
#
# Reads the VyOS config tree (set interfaces wwan wwanN …) and translates it
# into the nested dict expected by the WWAN FSM D-Bus service, then pushes the
# config via D-Bus SetConfiguration.
#
# This script replaces the upstream VyOS interfaces_wwan.py.

import asyncio
import ipaddress
import os
import re
import sys

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configverify import verify_vrf
from vyos.configverify import verify_mirror_redirect
from vyos.configverify import verify_mtu_ipv6
from vyos.ifconfig import WWANIf
from vyos.utils.network import interface_exists
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()

service_name = 'ModemManager.service'
manager_unit = 'igos-wwan-manager.service'


def _ensure_manager_running():
    """Idempotently start the WWAN manager service.

    The manager unit has NO [Install] section -- it is never started by
    systemd at boot.  conf_mode is the sole start path:
      - At boot, vyos-router.service replays the saved config, which
        runs this conf_mode, which starts the manager.
      - On a live `commit`, this same path starts it.
    `systemctl start` is a no-op if the unit is already active.

    NOTE: `systemctl start` returns as soon as the unit is *activating*,
    not when the python service has finished initialising and claimed
    its well-known D-Bus name (com.igos.IgosModemManager).  Callers
    therefore must tolerate the bus name not being on the bus yet --
    that retry is implemented in `_apply_via_dbus`.

    Once running, the manager owns its own lifecycle and the graceful
    teardown sequence on interface deletion -- we never stop it from
    conf_mode.  On a reboot with no wwan configured, conf_mode simply
    does not start the manager, so MM also stays down.
    """
    call(f'systemctl start {manager_unit}')

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _leaf(cfg, key, default=None):
    """Return a leaf value from a VyOS config dict, or *default*."""
    return cfg.get(key, default)


def _leaf_int(cfg, key, default=0):
    """Return a leaf value as int."""
    v = cfg.get(key)
    if v is None:
        return default
    return int(v)


def _leaf_exists(cfg, key):
    """True when a valueless node is present."""
    return key in cfg


def _csv_to_list(value, cast=str):
    """Split a comma-separated string into a list, stripping whitespace."""
    if not value:
        return []
    return [cast(x.strip()) for x in str(value).split(',') if x.strip()]


# ---------------------------------------------------------------------------
# get_config  — read the VyOS tree and return raw dict
# ---------------------------------------------------------------------------

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['interfaces', 'wwan']

    # get_interface_dict() handles VYOS_TAGNODE_VALUE, deleted detection,
    # key_mangling, defaults, and populates change-tracking keys needed by
    # Interface.update(): address_old, eui64_old, mac_old, is_bridge_member,
    # is_bond_member, is_mirror_intf, qos, etc.
    ifname, wwan = get_interface_dict(conf, base)

    # ── Live-tree intent flags ───────────────────────────────────────
    # get_interface_dict() merges XML <defaultValue> tags into the parsed
    # dict regardless of whether the user actually configured the parent
    # node.  For optional features (e.g. ip-passthrough), defaulted sub-leaves
    # would otherwise look indistinguishable from user-configured values.
    # We therefore stash explicit "the user touched this" flags here, sourced
    # from the live config tree, so verify() can reason about user intent
    # without being fooled by phantom defaults.
    iface_base = base + [ifname]
    wwan['_user_set'] = {
        'ip_passthrough': conf.exists(iface_base + ['ip-passthrough']),
        'ip_passthrough_interface': conf.exists(
            iface_base + ['ip-passthrough', 'interface']
        ),
        'ipv6_bridging_interface': conf.exists(
            iface_base + ['ipv6-bridging', 'interface']
        ),
        # IPv6 management-address — opt-in feature.  Presence of the
        # `management-address` node enables stamping; otherwise the FSM
        # leaves wwanN address-only.  `disable-default-https` is a
        # node-level flag that suppresses the auto-permit for TCP 443.
        'ipv6_mgmt_addr_configured': conf.exists(
            iface_base + ['ipv6', 'management-address']
        ),
        'ipv6_mgmt_addr_disable_default_https': conf.exists(
            iface_base + ['ipv6', 'management-address', 'disable-default-https']
        ),
        # DHCPv6 prefix delegation — when set, the FSM-installed egress
        # hygiene chain must permit DHCPv6 client traffic (UDP/546) so
        # dhcp6c can solicit an IA_PD from the carrier.  Otherwise the
        # chain drops it as forbidden upstream chatter.
        'dhcpv6_pd': conf.exists(iface_base + ['dhcpv6-options', 'pd']),
    }

    # ── IP passthrough conflict guard ────────────────────────────────────
    # bind-interfaces dnsmasq instances spawned by the FSM will silently
    # lose to (or steal from) any other DHCP/RA service running on the
    # same LAN port.  Stash live-tree existence flags so verify() can
    # raise a clean ConfigError instead of producing a confusing runtime
    # race between dnsmasq, kea, and radvd/router-advert.
    pt_iface_lookup = None
    if wwan['_user_set']['ip_passthrough_interface']:
        pt_iface_lookup = conf.return_value(
            iface_base + ['ip-passthrough', 'interface']
        )
    wwan['_passthrough_conflicts'] = {}
    if pt_iface_lookup:
        # dhcp-server conflict: only flag when *this* LAN interface is
        # explicitly listed as a listen-interface for some subnet.  The
        # previous predicate also matched any subnet that simply had
        # `default-router` set (which is true on virtually every
        # dhcp-server config) and produced false positives.
        dhcp_conflict = False
        if conf.exists(['service', 'dhcp-server', 'shared-network-name']):
            for sn in (conf.list_nodes(
                    ['service', 'dhcp-server', 'shared-network-name']) or []):
                for s in (conf.list_nodes(
                        ['service', 'dhcp-server', 'shared-network-name',
                         sn, 'subnet']) or []):
                    listen = conf.return_values(
                        ['service', 'dhcp-server', 'shared-network-name',
                         sn, 'subnet', s, 'listen-interface']) or []
                    if pt_iface_lookup in listen:
                        dhcp_conflict = True
                        break
                if dhcp_conflict:
                    break
        # Bridge / bond membership conflict: a passthrough interface
        # MUST be a standalone wired LAN port — a bind-interfaces dnsmasq
        # cannot serve a slave of a bridge or bond.
        bridge_master = None
        for br in (conf.list_nodes(['interfaces', 'bridge']) or []):
            members = conf.list_nodes(
                ['interfaces', 'bridge', br, 'member', 'interface']) or []
            if pt_iface_lookup in members:
                bridge_master = br
                break
        bond_master = None
        for bn in (conf.list_nodes(['interfaces', 'bonding']) or []):
            members = conf.list_nodes(
                ['interfaces', 'bonding', bn, 'member', 'interface']) or []
            if pt_iface_lookup in members:
                bond_master = bn
                break
        wwan['_passthrough_conflicts'] = {
            'dhcp_server': dhcp_conflict,
            'dhcpv6_server': conf.exists(
                ['service', 'dhcpv6-server', 'shared-network-name']
            ),
            'router_advert': conf.exists(
                ['service', 'router-advert', 'interface', pt_iface_lookup]
            ),
            'bridge_master': bridge_master,
            'bond_master': bond_master,
        }

    # ── IPv6 bridging conflict guard ─────────────────────────
    # Mirrors the passthrough check: if the user pointed ipv6-bridging at a
    # physical interface that is itself enslaved in a bridge or bond, the
    # address would be added to a slave that does not carry L3 — SLAAC
    # clients on the actual master would see nothing useful.  Stash the
    # conflict so verify() can raise a clean ConfigError instructing the
    # user to target the master interface instead.
    brg_iface_lookup = None
    if wwan['_user_set']['ipv6_bridging_interface']:
        brg_iface_lookup = conf.return_value(
            iface_base + ['ipv6-bridging', 'interface']
        )
    wwan['_ipv6_bridging_conflicts'] = {}
    if brg_iface_lookup:
        brg_bridge_master = None
        for br in (conf.list_nodes(['interfaces', 'bridge']) or []):
            if br == brg_iface_lookup:
                continue  # targeting the bridge itself is fine
            members = conf.list_nodes(
                ['interfaces', 'bridge', br, 'member', 'interface']) or []
            if brg_iface_lookup in members:
                brg_bridge_master = br
                break
        brg_bond_master = None
        for bn in (conf.list_nodes(['interfaces', 'bonding']) or []):
            if bn == brg_iface_lookup:
                continue  # targeting the bond itself is fine
            members = conf.list_nodes(
                ['interfaces', 'bonding', bn, 'member', 'interface']) or []
            if brg_iface_lookup in members:
                brg_bond_master = bn
                break
        wwan['_ipv6_bridging_conflicts'] = {
            'bridge_master': brg_bridge_master,
            'bond_master': brg_bond_master,
        }

    # ── IP Passthrough — Policy B coexistence check ──────────────────────
    # If the user designated a passthrough interface AND has set an explicit
    # 'interfaces ethernet <if> address ...', the FSM must NOT auto-provision
    # a management address (user wins).  Stamp the result into the dict so
    # build_fsm_config() can emit the correct policy decision.
    ipt = wwan.get('ip_passthrough', {}) or {}
    pt_iface = ipt.get('interface') if isinstance(ipt, dict) else None
    if pt_iface and wwan['_user_set']['ip_passthrough_interface']:
        eth_path = ['interfaces', 'ethernet', pt_iface, 'address']
        user_addrs = []
        if conf.exists(eth_path):
            user_addrs = conf.return_values(eth_path) or []
        wwan.setdefault('ip_passthrough', {})['_user_eth_addresses'] = user_addrs

    return wwan


# ---------------------------------------------------------------------------
# build_fsm_config  — translate VyOS dict → FSM nested dict
# ---------------------------------------------------------------------------

def build_fsm_config(wwan):
    """Produce the config dict expected by the FSM D-Bus SetConfiguration."""

    # ── SIM slots ────────────────────────────────────────────────────────
    sim_cfg = wwan.get('sim', {})
    slot_cfgs = sim_cfg.get('slot', {})

    # Global data-usage fallback values
    du = wwan.get('data_usage', {})
    global_data_limit_size = _leaf_int(du, 'size', 0)
    global_data_limit_action = _leaf(du, 'action', 'none')
    global_data_limit_billing = _leaf_int(du, 'billing_date', 1)
    global_data_limit_warning = _csv_to_list(du.get('warning', ''), int)

    # Both SIM slots are present and enabled by default. The CLI only
    # overrides per-slot settings; presence (or absence) of `slot N` in
    # the config tree does NOT determine enablement — only the explicit
    # `slot N disable` leaf disables a slot.
    sim_slots = []
    for slot_num in (1, 2):
        s = slot_cfgs.get(str(slot_num), {})
        dl = s.get('data_limit', {})
        sim_slots.append({
            'slot': slot_num,
            'enabled': not _leaf_exists(s, 'disable'),
            'apn': _leaf(s, 'apn', ''),
            'username': _leaf(s, 'username', ''),
            'password': _leaf(s, 'password', ''),
            'auth_type': _leaf(s, 'auth_type', 'none'),
            'pdp_type': _leaf(s, 'pdp_type', 'ipv4v6'),
            # Roaming is enabled by default; CLI 'disable-roaming' leaf turns it off.
            # Many aggregator/MVNO SIMs (e.g. roaming-style Rogers-on-Bell) only
            # connect when roaming is permitted, so 'enabled' is the safe default.
            'roaming': 'disabled' if _leaf_exists(s, 'disable_roaming') else 'enabled',
            'pin': _leaf(s, 'pin', ''),
            'puk': _leaf(s, 'puk', ''),
            'iccid': _leaf(s, 'iccid', ''),
            'supported_bands': _csv_to_list(
                _leaf(s, 'supported_bands', 'all')
            ),
            'preferred_carrier': _leaf(s, 'preferred_carrier', ''),
            'enable_network_scan': _leaf_exists(s, 'enable_network_scan'),
            'mtu': _leaf_int(s, 'mtu', 0),
            # Per-SIM data limits, falling back to global
            'data_limit_size': _leaf_int(dl, 'size', global_data_limit_size),
            'data_limit_action': _leaf(dl, 'action', global_data_limit_action),
            'data_limit_billing_date': _leaf_int(
                dl, 'billing_date', global_data_limit_billing
            ),
            'data_limit_warning': (
                _csv_to_list(dl.get('warning', ''), int)
                if dl.get('warning')
                else global_data_limit_warning
            ),
        })

    # ── Connectivity monitoring ──────────────────────────────────────────
    cm = wwan.get('connectivity_monitoring', {})
    connectivity_monitoring = {
        'enabled': not _leaf_exists(cm, 'disable'),
        'interval': _leaf_int(cm, 'interval', 60),
        'timeout': _leaf_int(cm, 'timeout', 10),
        'retry_count': _leaf_int(cm, 'retry_count', 3),
        'failure_threshold': _leaf_int(cm, 'failure_threshold', 2),
        'test_ipv4': not _leaf_exists(cm, 'disable_test_ipv4'),
        'test_ipv6': _leaf_exists(cm, 'test_ipv6'),
        'require_both': _leaf_exists(cm, 'require_both'),
        'ipv4_targets': _csv_to_list(
            _leaf(cm, 'ipv4_targets', '8.8.8.8,1.1.1.1')
        ),
        'ipv6_targets': _csv_to_list(
            _leaf(cm, 'ipv6_targets',
                  '2001:4860:4860::8888,2606:4700:4700::1111')
        ),
    }

    # ── Interface management ─────────────────────────────────────────────
    im = wwan.get('interface_management', {})
    interface_management = {
        'enabled': not _leaf_exists(im, 'disable'),
        'bearer_disconnect_delay': _leaf_int(im, 'bearer_disconnect_delay', 15),
        'registration_recovery_delay': _leaf_int(
            im, 'registration_recovery_delay', 20
        ),
        'registration_flap_count': _leaf_int(im, 'registration_flap_count', 5),
        'registration_flap_window': _leaf_int(
            im, 'registration_flap_window', 360
        ),
        'ip_change_delay': _leaf_int(im, 'ip_change_delay', 500),
        'ensure_link_up_on_connect': not _leaf_exists(
            im, 'disable_ensure_link_up_on_connect'
        ),
        'monitor_bearer_state': not _leaf_exists(
            im, 'disable_monitor_bearer_state'
        ),
        'monitor_ip_changes': not _leaf_exists(
            im, 'disable_monitor_ip_changes'
        ),
        'interface_up_timeout': _leaf_int(im, 'interface_up_timeout', 10),
    }

    # ── Enhanced reconnection ────────────────────────────────────────────
    rc = wwan.get('reconnection', {})
    ri = rc.get('retry_interval', {})
    enhanced_reconnection = {
        'enabled': not _leaf_exists(rc, 'disable_enhanced'),
        'signal_threshold': _leaf_int(rc, 'signal_threshold', -85),
        'retry_interval_good_signal': _leaf_int(ri, 'good_signal', 30),
        'retry_interval_poor_signal': _leaf_int(ri, 'poor_signal', 120),
        'max_wait_for_signal': _leaf_int(rc, 'max_wait_for_signal', 120),
        'signal_check_interval': _leaf_int(rc, 'signal_check_interval', 10),
        'signal_strength_buffer': _leaf_int(rc, 'signal_strength_buffer', 5),
    }

    # ── Failed-state retry ───────────────────────────────────────────────
    fr = wwan.get('failed_retry', {})
    failed_retry = {
        'enabled': not _leaf_exists(fr, 'disable'),
        'intervals': _csv_to_list(
            _leaf(fr, 'intervals', '600,1800,3600,7200'), int
        ),
        'max_interval': _leaf_int(fr, 'max_interval', 7200),
        'escalation_threshold': _leaf_int(fr, 'escalation_threshold', 3),
    }

    # ── SIM failover ─────────────────────────────────────────────────────
    sf = sim_cfg.get('sim_failover', {})
    fb = sim_cfg.get('sim_failback', {})

    # ── IPv6 bridging (carrier /64 to one downstream LAN) ────────────────
    brg = wwan.get('ipv6_bridging', {}) or {}
    brg_iface = brg.get('interface') if isinstance(brg, dict) else None
    ipv6_bridging = {
        'enabled': bool(brg_iface) and wwan['_user_set']['ipv6_bridging_interface'],
        'interface': brg_iface or '',
        'reconciliation_interval': _leaf_int(brg, 'reconciliation_interval', 10),
    }

    # ── IPv6 management-address (FSM-stamped <prefix>::host-id on wwanN) ─
    # Opt-in: enabled only when the user creates the `management-address`
    # node.  When enabled the FSM stamps <prefix>::host-id on wwanN and
    # installs an ip6tables chain that permits ICMPv6, ESTABLISHED/RELATED,
    # and (unless `disable-default-https` is set) TCP 443.  Additional
    # ports are opened via permit-tcp / permit-udp; permit-source narrows
    # every permit (including the default-443) to listed source prefixes.
    # Mutually exclusive with `ip-passthrough` (verify() refuses both).
    ipv6_mgmt_node = (wwan.get('ipv6', {}) or {}).get('management_address', {}) or {}
    def _as_list(v):
        if not v:
            return []
        return v if isinstance(v, list) else [v]
    mgmt_configured = wwan['_user_set'].get('ipv6_mgmt_addr_configured', False)
    ipv6_management_address = {
        'enabled': mgmt_configured and (not wwan['_user_set'].get('ip_passthrough')),
        'host_id': _leaf(ipv6_mgmt_node, 'host_id', '::1'),
        'disable_default_https': wwan['_user_set'].get(
            'ipv6_mgmt_addr_disable_default_https', False),
        'permit_tcp': [int(p) for p in _as_list(ipv6_mgmt_node.get('permit_tcp'))],
        'permit_udp': [int(p) for p in _as_list(ipv6_mgmt_node.get('permit_udp'))],
        'permit_source': _as_list(ipv6_mgmt_node.get('permit_source')),
    }

    # ── Timeouts ─────────────────────────────────────────────────────────
    to = wwan.get('timeouts', {})

    # ── Logging ──────────────────────────────────────────────────────────
    lg = wwan.get('logging', {})

    # ── IP Passthrough (DOCSIS-modem-style) ──────────────────────────────
    ipt = wwan.get('ip_passthrough', {}) or {}
    pt_iface = ipt.get('interface') if isinstance(ipt, dict) else None
    if pt_iface:
        # Policy B: only emit a default mgmt address when the user has NOT
        # set 'interfaces ethernet <if> address ...' on the passthrough port.
        user_eth_addrs = ipt.get('_user_eth_addresses') or []
        user_owns_eth = bool(user_eth_addrs)
        mgmt_v4_cidr = (
            '' if user_owns_eth
            else _leaf(ipt, 'management_address', '192.168.200.1/24')
        )
        mgmt_v6_cidr = (
            '' if user_owns_eth
            else _leaf(ipt, 'management_address_ipv6', 'fd00:6c61:6e30::1/64')
        )
        # Pre-resolve bare-IP forms (no /CIDR) for use as DHCPv4 option 3
        # router and DHCPv6 advertised gateway.  RFC-strict clients (Windows)
        # reject leases with router=0.0.0.0, so we always supply a real IP
        # when one is available — either FSM-owned default or the user's
        # first ethernet address under Policy B.
        def _bare_ip(cidr: str, want_v6: bool = False) -> str:
            if not cidr:
                return ''
            try:
                ip = ipaddress.ip_interface(cidr).ip
            except (ValueError, TypeError):
                return ''
            if want_v6 and ip.version != 6:
                return ''
            if not want_v6 and ip.version != 4:
                return ''
            return str(ip)
        if user_owns_eth:
            mgmt_v4_ip = next(
                (_bare_ip(a) for a in user_eth_addrs if _bare_ip(a)), '')
            mgmt_v6_ip = next(
                (_bare_ip(a, want_v6=True) for a in user_eth_addrs
                 if _bare_ip(a, want_v6=True)), '')
        else:
            mgmt_v4_ip = _bare_ip(mgmt_v4_cidr)
            mgmt_v6_ip = _bare_ip(mgmt_v6_cidr, want_v6=True)
        ip_passthrough = {
            'enabled': True,
            'interface': pt_iface,
            'mac': _leaf(ipt, 'mac', '') or '',
            'lease_time': _leaf_int(ipt, 'lease_time', 60),
            'management_address': mgmt_v4_cidr,
            'management_address_ipv6': mgmt_v6_cidr,
            'mgmt_owned_by_user': user_owns_eth,
            'mgmt_v4_ip': mgmt_v4_ip,
            'mgmt_v6_ip': mgmt_v6_ip,
            # TCP MSS clamping on WWAN egress — ON by default,
            # industry-standard for cellular CPE passthrough.
            # Transparently fixes non-compliant downstream
            # clients that ignore DHCP option 26 / RA MTU.  Disable only for
            # PMTUD debugging.
            'mss_clamp_enabled': not _leaf_exists(ipt, 'disable_mss_clamp'),
            # Optional user-supplied DNS override (multi-value). When set,
            # these resolvers are advertised to the downstream device in
            # place of carrier-supplied DNS.
            'dns_servers': (
                ipt.get('dns_server')
                if isinstance(ipt.get('dns_server'), list)
                else ([ipt.get('dns_server')] if ipt.get('dns_server') else [])
            ),
        }
    else:
        ip_passthrough = {'enabled': False}

    # ── Assemble the complete config dict ────────────────────────────────
    config = {
        # Basic interface settings
        'interface_disabled': _leaf_exists(wwan, 'disable'),
        'primary_sim_slot': _leaf_int(sim_cfg, 'primary_slot', 1),
        'connection_mode': _leaf(wwan, 'connection_mode', 'always-on'),

        # MTU
        'mtu': _leaf_int(wwan, 'mtu', 1420),

        # Enhanced reconnection
        'enhanced_reconnection': enhanced_reconnection,

        # APN discovery
        'android_apn_discovery': (
            'disabled' if _leaf_exists(
                wwan.get('apn_discovery', {}), 'disable'
            ) else 'enabled'
        ),

        # SIM failover (global enable + policy)
        'sim_failover': (
            'disabled' if _leaf_exists(sf, 'disable') else 'enabled'
        ),
        'sim_failover_connect_retries': _leaf_int(
            sf, 'connect_retries', 3
        ),
        'sim_failover_revert_timer': _leaf_int(sf, 'revert_timer', 300),
        'sim_failover_signal_loss_timer': _leaf_int(
            sf, 'signal_loss_timer', 60
        ),
        'sim_failover_signal_threshold': _leaf_int(
            sf, 'signal_threshold', -90
        ),

        # SIM failback
        'sim_failback_enabled': not _leaf_exists(fb, 'disable'),
        'sim_failback_check_interval': _leaf_int(
            fb, 'check_interval', 600
        ),

        # Data usage (global monitoring interval)
        'data_usage_monitoring_interval': _leaf_int(
            du, 'monitoring_interval', 30
        ),

        # Hardware reset
        'hardware_reset_enabled': not _leaf_exists(
            wwan.get('hardware_reset', {}), 'disable'
        ),
        'max_hardware_resets': _leaf_int(
            wwan.get('hardware_reset', {}), 'max_attempts', 3
        ),
        'hardware_reset_cooldown': _leaf_int(
            wwan.get('hardware_reset', {}), 'cooldown', 300
        ),

        # Connection and timeout settings
        'connection_timeout': _leaf_int(to, 'connection', 120),
        'registration_timeout': _leaf_int(to, 'registration', 180),
        'network_scan_timeout': _leaf_int(
            wwan.get('network_scan', {}), 'timeout', 60
        ),
        'network_mode': _leaf(wwan, 'network_mode', 'auto'),

        # Monitoring intervals
        'normal_monitoring_interval': _leaf_int(
            to, 'normal_monitoring_interval', 30
        ),

        # Logging
        'verbose_logging': not _leaf_exists(lg, 'disable_verbose'),
        'log_level': _leaf(lg, 'level', 'info'),
        'log_sink': _leaf(lg, 'sink', 'both'),

        # Collections
        'sim_slots': sim_slots,
        'connectivity_monitoring': connectivity_monitoring,
        'interface_management': interface_management,
        'failed_retry': failed_retry,

        # IPv6 bridging (carrier /64 -> one downstream LAN; mutually exclusive
        # with ip-passthrough — see verify())
        'ipv6_bridging': ipv6_bridging,

        # IPv6 management-address (FSM-stamped <prefix>::host-id on wwanN;
        # mutually exclusive with ip-passthrough — see verify())
        'ipv6_management_address': ipv6_management_address,

        # IP Passthrough (mutually exclusive with ipv6-bridging — see verify())
        'ip_passthrough': ip_passthrough,

        # DHCPv6 PD configured — gates the egress-hygiene chain so DHCPv6
        # client traffic (UDP/546) is allowed upstream.  Derived from the
        # live-tree existence of `dhcpv6-options pd` (see _user_set).
        'dhcpv6_pd_enabled': bool(wwan['_user_set'].get('dhcpv6_pd')),
    }

    return config


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

def verify(wwan):
    if 'deleted' in wwan:
        return None

    verify_vrf(wwan)
    verify_mtu_ipv6(wwan)
    verify_mirror_redirect(wwan)

    # ── IP Passthrough verification ──────────────────────────────────────
    # Reason about user intent via live-tree flags stashed by get_config(),
    # not the defaults-merged dict (XML <defaultValue> tags would otherwise
    # make unconfigured sub-leaves indistinguishable from user-set ones).
    user_set = wwan.get('_user_set', {})
    if user_set.get('ip_passthrough'):
        if not user_set.get('ip_passthrough_interface'):
            raise ConfigError(
                "ip-passthrough sub-options require 'ip-passthrough "
                "interface <eth>' to be set first."
            )
        # Mutually exclusive with ipv6-bridging — both consume the bearer's
        # IPv6 prefix.
        if user_set.get('ipv6_bridging_interface'):
            raise ConfigError(
                "ip-passthrough is mutually exclusive with ipv6-bridging — "
                "both consume the bearer's IPv6 prefix.  Remove one or the "
                "other."
            )
        # Conflict guard: bind-interfaces dnsmasq cannot coexist with
        # another service trying to serve DHCP / RA on the same LAN port.
        conflicts = wwan.get('_passthrough_conflicts', {}) or {}
        if conflicts.get('dhcp_server'):
            raise ConfigError(
                "ip-passthrough conflicts with 'service dhcp-server' "
                "on the same LAN interface — both would try to bind "
                "UDP/67.  Disable one or the other."
            )
        if conflicts.get('dhcpv6_server'):
            raise ConfigError(
                "ip-passthrough conflicts with 'service dhcpv6-server' "
                "— both would try to bind DHCPv6 on UDP/547.  Disable "
                "one or the other."
            )
        if conflicts.get('router_advert'):
            raise ConfigError(
                "ip-passthrough conflicts with 'service router-advert' "
                "on the same LAN interface — both would emit RAs.  "
                "Disable one or the other."
            )
        if conflicts.get('bridge_master'):
            raise ConfigError(
                f"ip-passthrough interface is a member of bridge "
                f"'{conflicts['bridge_master']}' — the designated LAN "
                f"port must be a standalone wired interface."
            )
        if conflicts.get('bond_master'):
            raise ConfigError(
                f"ip-passthrough interface is a member of bond "
                f"'{conflicts['bond_master']}' — the designated LAN "
                f"port must be a standalone wired interface."
            )

    # ── ipv6-bridging guard ── must target the L3-owning interface ────────
    brg_conflicts = wwan.get('_ipv6_bridging_conflicts', {}) or {}
    if brg_conflicts.get('bridge_master'):
        raise ConfigError(
            f"ipv6-bridging interface is a member of bridge "
            f"'{brg_conflicts['bridge_master']}' — point ipv6-bridging "
            f"at '{brg_conflicts['bridge_master']}' instead so the "
            f"carrier prefix lands on the L3-owning interface."
        )
    if brg_conflicts.get('bond_master'):
        raise ConfigError(
            f"ipv6-bridging interface is a member of bond "
            f"'{brg_conflicts['bond_master']}' — point ipv6-bridging "
            f"at '{brg_conflicts['bond_master']}' instead so the "
            f"carrier prefix lands on the L3-owning interface."
        )

    # ── IPv6 management-address guard ────────────────────────────────────
    # The FSM stamps `<carrier-prefix>::host-id` on wwanN whenever the
    # bearer has IPv6 and ip-passthrough is not configured.  Passthrough
    # hands the entire carrier prefix to a downstream device — there is
    # no FSM-owned IP on wwanN to attach to — so the two are mutually
    # exclusive.
    if user_set.get('ipv6_mgmt_addr_configured') and \
            user_set.get('ip_passthrough'):
        raise ConfigError(
            "'ipv6 management-address' is mutually exclusive with "
            "'ip-passthrough' — passthrough hands the carrier IPv6 to "
            "a downstream device, leaving no FSM-owned address on the "
            "WWAN interface.  Remove one or the other."
        )

    return None


# ---------------------------------------------------------------------------
# generate  — nothing to render
# ---------------------------------------------------------------------------

def generate(wwan):
    return None


# ---------------------------------------------------------------------------
# apply  — push config to FSM via D-Bus
# ---------------------------------------------------------------------------

def apply(wwan):
    ifname = wwan.get('ifname', 'wwan0')
    # Extract numeric interface index from wwanN
    match = re.search(r'(\d+)$', ifname)
    interface_number = int(match.group(1)) if match else 0

    if 'deleted' in wwan:
        # Interface node is gone from the CLI tree — fully tear down on
        # the FSM side: shut the state machine down, unexport the D-Bus
        # object, and delete the persisted config cache so a later
        # service restart will NOT replay a stale configuration.
        #
        # NOTE: we intentionally do NOT stop the manager service or
        # ModemManager here, even when this is the last wwan interface.
        # The manager owns the graceful teardown sequence (drop bearer,
        # release session, unmanage the modem) and stopping it mid-flight
        # would skip that.  At next boot, with no wwan configured, the
        # conf_mode replay simply will not start the manager -- so the
        # "no config => no MM running" goal is met on reboot, while a
        # live `delete` still gets a clean teardown.
        # Ensure the manager is available so RemoveInterface can succeed even
        # if this commit path is the first WWAN action after a service crash.
        _ensure_manager_running()
        removed = asyncio.run(_remove_via_dbus(interface_number))
        if not removed:
            # Do not block commit, but ensure stale persisted state does not
            # resurrect when the interface is recreated later.
            _remove_local_wwan_cache(interface_number)

        if interface_exists(ifname):
            w = WWANIf(ifname)
            w.remove()

        return None

    if _leaf_exists(wwan, 'disable'):
        # Admin-disable — keep the FSM/D-Bus object around but tell it to
        # drop the bearer and suppress activity.  Persisted config is
        # retained so re-enable picks up the previous configuration.
        config = {'interface_disabled': True}
        _ensure_manager_running()
        asyncio.run(_apply_via_dbus(interface_number, config))

        if interface_exists(ifname):
            w = WWANIf(ifname)
            w.remove()

        return None

    config = build_fsm_config(wwan)

    # Ensure the WWAN manager service is running -- it owns the D-Bus
    # endpoint we are about to call and is responsible for starting
    # ModemManager.  The unit has no [Install] section, so conf_mode is
    # the only thing that ever starts it.  Idempotent: a no-op if
    # already active.
    _ensure_manager_running()

    # Send config via D-Bus
    asyncio.run(_apply_via_dbus(interface_number, config))

    # Apply VyOS infrastructure settings to the kernel interface:
    # VRF, mirror/redirect, ip/ipv6 options, MTU, description, etc.
    if interface_exists(ifname):
        w = WWANIf(ifname)
        w.update(wwan)

    return None


async def _apply_via_dbus(interface_number, config, connect_timeout=20.0):
    """Push configuration to the FSM D-Bus service.

    Retries the initial connect for up to *connect_timeout* seconds.
    The manager service is started just before this call by
    `_ensure_manager_running()`, but `systemctl start` returns while the
    python process is still booting and has not yet claimed its D-Bus
    well-known name (`com.igos.IgosModemManager`).  Without a retry the
    very first `commit` after a fresh boot fails with
    "name was not provided by any .service files".
    """
    # Import here to avoid hard dependency at module level
    from vyos.utils.wwan.wwan_client import WWANClient, WWANError
    import time

    deadline = time.monotonic() + connect_timeout
    last_exc = None
    while True:
        try:
            async with WWANClient() as client:
                await client.add_interface(interface_number)
                await asyncio.sleep(0.5)
                result = await client.set_configuration(
                    interface_number, config)
                print(f'WWAN interface {interface_number}: {result}')
            return
        except WWANError as exc:
            # WWANError covers both "bus name not on the bus" and
            # genuine method errors.  Treat name-not-found as transient
            # only while we are still within the connect timeout; any
            # other WWANError is a real configuration failure.
            msg = str(exc)
            transient = (
                'was not provided by any .service files' in msg
                or 'NameHasNoOwner' in msg
                or 'ServiceUnknown' in msg
            )
            last_exc = exc
            if transient and time.monotonic() < deadline:
                await asyncio.sleep(0.5)
                continue
            raise ConfigError(
                f'WWAN D-Bus configuration failed: {exc}') from exc
        except Exception as exc:
            last_exc = exc
            if time.monotonic() < deadline:
                # Treat unexpected connect-time errors as transient
                # until the timeout expires (covers DBus transport-level
                # races during service start).
                await asyncio.sleep(0.5)
                continue
            raise ConfigError(
                f'Failed to communicate with WWAN service: {exc}'
            ) from exc


async def _remove_via_dbus(interface_number):
    """Tell the FSM service to fully remove an interface.

    Calls ``RemoveInterface`` on the WWAN D-Bus service which shuts the
    FSM down, unexports the per-interface D-Bus object, and deletes the
    persisted JSON config cache.  Without this step a subsequent service
    restart would replay the last-known configuration even though the
    user has removed the interface from the VyOS CLI tree.

    Failures are surfaced as warnings rather than ConfigError so that a
    transient D-Bus issue does not block a `commit` that is otherwise
    deleting state (the on-disk cache will be cleaned up on next start).
    """
    from vyos.utils.wwan.wwan_client import WWANClient, WWANError
    import time

    deadline = time.monotonic() + 20.0
    while True:
        try:
            async with WWANClient() as client:
                result = await client.remove_interface(interface_number)
                print(f'WWAN interface {interface_number}: {result}')
                return True
        except WWANError as exc:
            msg = str(exc)
            transient = (
                'was not provided by any .service files' in msg
                or 'NameHasNoOwner' in msg
                or 'ServiceUnknown' in msg
            )
            if transient and time.monotonic() < deadline:
                await asyncio.sleep(0.5)
                continue
            print(f'Warning: WWAN RemoveInterface failed: {exc}')
            return False
        except Exception as exc:
            if time.monotonic() < deadline:
                await asyncio.sleep(0.5)
                continue
            print(f'Warning: failed to communicate with WWAN service: {exc}')
            return False


def _remove_local_wwan_cache(interface_number):
    """Best-effort cleanup for per-interface runtime cache files.

    This is a fallback when D-Bus RemoveInterface cannot be reached.
    Prevents deleted interfaces from replaying stale state when recreated.
    """
    base = f'/run/wwan/interface{interface_number}.conf'
    for path in (base, base + '.bad'):
        try:
            os.unlink(path)
            print(f'WWAN interface {interface_number}: removed stale cache {path}')
        except FileNotFoundError:
            pass
        except Exception as exc:
            print(f'Warning: failed to remove WWAN cache {path}: {exc}')


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
