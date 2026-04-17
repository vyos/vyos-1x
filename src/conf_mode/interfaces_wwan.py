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
import re
import sys

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configverify import verify_vrf
from vyos.configverify import verify_mirror_redirect
from vyos.configverify import verify_mtu_ipv6
from vyos.ifconfig import WWANIf
from vyos.utils.network import interface_exists
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

    sim_slots = []
    for slot_num in sorted(slot_cfgs.keys(), key=int):
        s = slot_cfgs[slot_num]
        dl = s.get('data_limit', {})
        sim = {
            'slot': int(slot_num),
            'enabled': not _leaf_exists(s, 'disable'),
            'apn': _leaf(s, 'apn', ''),
            'username': _leaf(s, 'username', ''),
            'password': _leaf(s, 'password', ''),
            'auth_type': _leaf(s, 'auth_type', 'none'),
            'pdp_type': _leaf(s, 'pdp_type', 'ipv4v6'),
            'roaming': 'enabled' if _leaf_exists(s, 'roaming') else 'disabled',
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
        }
        sim_slots.append(sim)

    # If no SIM slots explicitly configured, create a default slot 1
    if not sim_slots:
        sim_slots.append({
            'slot': 1,
            'enabled': True,
            'apn': '',
            'username': '',
            'password': '',
            'auth_type': 'none',
            'pdp_type': 'ipv4v6',
            'roaming': 'disabled',
            'pin': '',
            'puk': '',
            'iccid': '',
            'supported_bands': ['all'],
            'preferred_carrier': '',
            'enable_network_scan': False,
            'mtu': 0,
            'data_limit_size': global_data_limit_size,
            'data_limit_action': global_data_limit_action,
            'data_limit_billing_date': global_data_limit_billing,
            'data_limit_warning': global_data_limit_warning,
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
        'retry_interval_good_signal': _leaf_int(ri, 'good_signal', 15),
        'retry_interval_poor_signal': _leaf_int(ri, 'poor_signal', 45),
        'max_wait_for_signal': _leaf_int(rc, 'max_wait_for_signal', 120),
        'signal_check_interval': _leaf_int(rc, 'signal_check_interval', 10),
        'signal_strength_buffer': _leaf_int(rc, 'signal_strength_buffer', 5),
    }

    # ── Failed-state retry ───────────────────────────────────────────────
    fr = wwan.get('failed_retry', {})
    failed_retry = {
        'enabled': not _leaf_exists(fr, 'disable'),
        'intervals': _csv_to_list(
            _leaf(fr, 'intervals', '300,600,1200,1800'), int
        ),
        'max_interval': _leaf_int(fr, 'max_interval', 1800),
        'escalation_threshold': _leaf_int(fr, 'escalation_threshold', 3),
    }

    # ── SIM failover ─────────────────────────────────────────────────────
    sf = sim_cfg.get('sim_failover', {})
    fb = sim_cfg.get('sim_failback', {})

    # ── PD ───────────────────────────────────────────────────────────────
    pd_cfg = wwan.get('pd', {})
    pd_list = []
    for pd_id in sorted(pd_cfg.keys(), key=int):
        pd_entry = pd_cfg[pd_id]
        iface_cfgs = pd_entry.get('interface', {})
        interfaces = {}
        for iface_name, iface_data in iface_cfgs.items():
            interfaces[iface_name] = {
                'address': _leaf_int(iface_data, 'address', 0),
                'sla_id': _leaf_int(iface_data, 'sla_id', 0),
                'sla_len': iface_data.get('sla_len'),  # None = auto
            }
        pd_list.append({
            'id': int(pd_id),
            'interfaces': interfaces,
        })

    # ── Timeouts ─────────────────────────────────────────────────────────
    to = wwan.get('timeouts', {})

    # ── Logging ──────────────────────────────────────────────────────────
    lg = wwan.get('logging', {})

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
        'snmp_monitoring': not _leaf_exists(lg, 'disable_snmp_monitoring'),
        'detailed_status': not _leaf_exists(lg, 'disable_detailed_status'),

        # Collections
        'sim_slots': sim_slots,
        'connectivity_monitoring': connectivity_monitoring,
        'interface_management': interface_management,
        'failed_retry': failed_retry,

        # IPv6 Prefix Delegation
        'pd': pd_list,
        'pd_reconciliation_interval': _leaf_int(
            wwan, 'pd_reconciliation_interval', 10
        ),
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

    if 'deleted' in wwan or _leaf_exists(wwan, 'disable'):
        # Interface is being removed or disabled — tell the FSM
        config = {'interface_disabled': True}
        asyncio.run(_apply_via_dbus(interface_number, config))

        if interface_exists(ifname):
            w = WWANIf(ifname)
            w.remove()
        return None

    config = build_fsm_config(wwan)

    # Send config via D-Bus
    asyncio.run(_apply_via_dbus(interface_number, config))

    # Apply VyOS infrastructure settings to the kernel interface:
    # VRF, mirror/redirect, ip/ipv6 options, MTU, description, etc.
    if interface_exists(ifname):
        w = WWANIf(ifname)
        w.update(wwan)
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
