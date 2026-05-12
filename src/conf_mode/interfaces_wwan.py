#!/usr/bin/env python3
#
# Copyright (C) 2024-2026 IGOS and contributors
# SPDX-License-Identifier: GPL-2.0-or-later
#
# interfaces_wwan.py — VyOS conf_mode script for enhanced WWAN interface.
#
# Reads the VyOS config tree (set interfaces wwan wwanN …) and translates it
# into the nested dict expected by the WWAN FSM D-Bus service, then pushes the
# config via D-Bus SetConfiguration.
#
# This script replaces the upstream VyOS interfaces_wwan.py and the flat-file
# interfaces_wwan2.py config parser.

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

    # ── SNMP trap target lookup ──────────────────────────────────────
    # Resolve the first `service snmp trap-target` entry (v2c only) from the
    # live tree and stash for apply()-time use.  Done here (not in apply())
    # so the file has exactly one Config() instance — required by
    # tests/test_configd_inspect.py::test_file_config_instance.
    snmp_base = ['service', 'snmp', 'trap-target']
    snmp_dest = None
    snmp_community = None
    if conf.exists(snmp_base):
        targets = conf.list_nodes(snmp_base) or []
        if targets:
            addr = targets[0]
            sub = snmp_base + [addr]
            port = conf.return_value(sub + ['port']) or '162'
            community = conf.return_value(sub + ['community']) or 'public'
            snmp_dest = f'udp:{addr}:{port}'
            snmp_community = community
    wwan['_snmp_trap'] = {
        'dest': snmp_dest,
        'community': snmp_community,
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
            # TCP MSS clamping on WWAN egress — ON by default, matches
            # commercial cellular passthrough products (Cradlepoint, Peplink,
            # Sierra, Digi).  Transparently fixes non-compliant downstream
            # clients that ignore DHCP option 26 / RA MTU.  Disable only for
            # PMTUD debugging.
            'mss_clamp_enabled': not _leaf_exists(ipt, 'disable_mss_clamp'),
            # Optional user-supplied DNS override (multi-value). When set,
            # these resolvers are advertised to the downstream device in
            # place of carrier-supplied DNS. Mirrors Cradlepoint/Peplink.
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
        'system_health_check_interval': _leaf_int(
            lg, 'health_check_interval', 300
        ),

        # Logging (all default enabled — disable nodes to turn off)
        'verbose_logging': not _leaf_exists(lg, 'disable_verbose'),
        'log_level': _leaf(lg, 'level', 'info'),
        'log_sink': _leaf(lg, 'sink', 'both'),
        'snmp_monitoring': not _leaf_exists(lg, 'disable_snmp_monitoring'),
        'detailed_status': not _leaf_exists(lg, 'disable_detailed_status'),

        # Collections
        'sim_slots': sim_slots,
        'connectivity_monitoring': connectivity_monitoring,
        'interface_management': interface_management,
        'failed_retry': failed_retry,

        # IPv6 bridging (carrier /64 -> one downstream LAN; mutually exclusive
        # with ip-passthrough — see verify())
        'ipv6_bridging': ipv6_bridging,

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

    return None


# ---------------------------------------------------------------------------
# generate  — nothing to render
# ---------------------------------------------------------------------------

def generate(wwan):
    return None


# ---------------------------------------------------------------------------
# SNMP trap emitter integration
# ---------------------------------------------------------------------------

# /etc/default/igos-wwan-snmp-traps gates the trap unit via
# ConditionPathExists= in igos-wwan-snmp-traps.service.  Writing it (with a
# valid IGOS_SNMPTRAP_DEST) enables the daemon; removing it disables.
_SNMP_TRAPS_DEFAULTS_FILE = '/etc/default/igos-wwan-snmp-traps'
_SNMP_TRAPS_UNIT = 'igos-wwan-snmp-traps.service'


def _resolve_snmp_trap_dest(wwan):
    """Return (dest, community) stashed by get_config(), or (None, None).

    The actual lookup happens in get_config() to keep this file at a single
    Config() instantiation (enforced by test_configd_inspect).
    """
    info = wwan.get('_snmp_trap') or {}
    return info.get('dest'), info.get('community')


def _sync_snmp_trap_unit(wwan):
    """Render /etc/default/igos-wwan-snmp-traps and start/stop the unit.

    The trap emitter runs iff:
      - `service snmp trap-target` is configured (we have somewhere to send
        traps), AND
      - the wwan interface does not have `logging disable-snmp-monitoring`.
    """
    lg = wwan.get('logging', {})
    snmp_disabled_for_iface = _leaf_exists(lg, 'disable_snmp_monitoring')
    iface_gone = ('deleted' in wwan) or _leaf_exists(wwan, 'disable')

    dest, community = _resolve_snmp_trap_dest(wwan)

    enable = (
        dest is not None
        and not snmp_disabled_for_iface
        and not iface_gone
    )

    if enable:
        body = (
            '# Auto-generated by interfaces_wwan.py — do not edit by hand.\n'
            f'IGOS_SNMPTRAP_DEST={dest}\n'
            f'IGOS_SNMPTRAP_COMMUNITY={community}\n'
            'IGOS_SNMPTRAP_BIN=/usr/bin/snmptrap\n'
        )
        # Atomic write
        tmp = _SNMP_TRAPS_DEFAULTS_FILE + '.tmp'
        with open(tmp, 'w') as f:
            f.write(body)
        os.replace(tmp, _SNMP_TRAPS_DEFAULTS_FILE)
        call(f'systemctl reload-or-restart {_SNMP_TRAPS_UNIT}')
    else:
        # Tear down: stop the unit (no-op if already stopped) and remove
        # the gating file so it stays down across reboots.
        call(f'systemctl stop {_SNMP_TRAPS_UNIT}')
        try:
            os.unlink(_SNMP_TRAPS_DEFAULTS_FILE)
        except FileNotFoundError:
            pass


# ---------------------------------------------------------------------------
# apply  — push config to FSM via D-Bus
# ---------------------------------------------------------------------------

def apply(wwan):
    ifname = wwan.get('ifname', 'wwan0')
    # Extract numeric interface index from wwanN
    match = re.search(r'(\d+)$', ifname)
    interface_number = int(match.group(1)) if match else 0

    if 'deleted' in wwan or _leaf_exists(wwan, 'disable'):
        # Interface is being removed or disabled — tell the FSM
        config = {'interface_disabled': True}
        asyncio.run(_apply_via_dbus(interface_number, config))

        if interface_exists(ifname):
            w = WWANIf(ifname)
            w.remove()

        # Stop the trap emitter (no live wwan interface to source alerts).
        try:
            _sync_snmp_trap_unit(wwan)
        except Exception as exc:
            print(f'Warning: failed to sync WWAN SNMP trap unit: {exc}')
        return None

    config = build_fsm_config(wwan)

    # Send config via D-Bus
    asyncio.run(_apply_via_dbus(interface_number, config))

    # Apply VyOS infrastructure settings to the kernel interface:
    # VRF, mirror/redirect, ip/ipv6 options, MTU, description, etc.
    if interface_exists(ifname):
        w = WWANIf(ifname)
        w.update(wwan)

    # Sync the SNMP trap emitter unit with current SNMP + WWAN logging
    # config (best-effort — failures should not block the commit).
    try:
        _sync_snmp_trap_unit(wwan)
    except Exception as exc:
        print(f'Warning: failed to sync WWAN SNMP trap unit: {exc}')

    return None


async def _apply_via_dbus(interface_number, config):
    """Push configuration to the FSM D-Bus service."""
    # Import here to avoid hard dependency at module level
    from vyos.utils.wwan.wwan_client import WWANClient, WWANError

    try:
        async with WWANClient() as client:
            await client.add_interface(interface_number)
            await asyncio.sleep(0.5)
            result = await client.set_configuration(interface_number, config)
            print(f'WWAN interface {interface_number}: {result}')
    except WWANError as exc:
        raise ConfigError(f'WWAN D-Bus configuration failed: {exc}') from exc
    except Exception as exc:
        raise ConfigError(
            f'Failed to communicate with WWAN service: {exc}'
        ) from exc


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
