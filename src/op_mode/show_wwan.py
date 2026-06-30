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
#
# Op-mode script for WWAN modem status display.
# All data comes from the WWAN FSM service via wwan_client — no raw QMI,
# avoiding conflicts with ModemManager.

import sys
import ast
import shutil
import textwrap

import vyos.opmode

from vyos.configquery import ConfigTreeQuery


def _get_interface_number(interface: str) -> int:
    """Extract numeric index from interface name (e.g. 'wwan0' -> 0)."""
    return int(interface.replace('wwan', ''))


def _get_client():
    """Return a WWANClientSync instance."""
    from vyos.utils.wwan.wwan_client import WWANClientSync
    return WWANClientSync()


def _get_full_status(interface: str) -> dict:
    """Fetch the full FSM status dict for an interface."""
    config = ConfigTreeQuery()
    if not config.exists(['interfaces', 'wwan', interface]):
        raise vyos.opmode.UnconfiguredSubsystem(
            f'Interface "{interface}" is not configured'
        )

    if_num = _get_interface_number(interface)
    try:
        client = _get_client()
        return client.get_status(if_num)
    except Exception as e:
        raise vyos.opmode.DataUnavailable(
            f'Cannot reach WWAN service for {interface}: {e}'
        )


def _normalize_list_field(value) -> list[str]:
    """Return a clean list for fields that may arrive as stringified lists."""
    if value is None or value == '':
        return []

    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value if v not in ('', None)]

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []

        # Common case from D-Bus marshalling layers: "['a', 'b']"
        if (text.startswith('[') and text.endswith(']')) or (
            text.startswith('(') and text.endswith(')')
        ):
            try:
                parsed = ast.literal_eval(text)
                if isinstance(parsed, (list, tuple, set)):
                    return [str(v) for v in parsed if v not in ('', None)]
            except (ValueError, SyntaxError):
                pass

        return [text]

    return [str(value)]


# ── Raw data helpers (return dicts for JSON mode) ───────────────────────

def _raw_status(status: dict) -> dict:
    return {
        'interface': status.get('interface_name', ''),
        'state': status.get('fsm_state', ''),
        'connection_mode': status.get('connection_mode', ''),
        'modem_state': status.get('modem_state', ''),
        'power_state': status.get('modem_power_state_name', ''),
        'access_technology': status.get('access_technology_name', ''),
        'operator': status.get('operator_name', ''),
        'operator_code': status.get('operator_code', ''),
        'registration_state': status.get('registration_state', ''),
        'apn': status.get('connected_apn', ''),
        'requested_apn': status.get('requested_apn', ''),
        'negotiated_apn': status.get('negotiated_apn', ''),
        'ipv4_address': status.get('ipv4_address', ''),
        'ipv6_address': status.get('ipv6_address', ''),
        'ipv4_gateway': status.get('ipv4_gateway', ''),
        'ipv6_gateway': status.get('ipv6_gateway', ''),
        'ipv4_dns': status.get('ipv4_dns', ''),
        'ipv6_dns': status.get('ipv6_dns', ''),
        'mtu': status.get('mtu_effective', status.get('mtu', '')),
        'signal_percent': status.get('signal_percent', 0),
        'signal_dbm': status.get('signal_dbm', 0),
        'current_bands': _normalize_list_field(status.get('current_bands', [])),
        'configured_bands': _normalize_list_field(status.get('configured_bands', [])),
        'session_rx_bytes': status.get('session_rx_bytes', 0),
        'session_tx_bytes': status.get('session_tx_bytes', 0),
        'session_duration': status.get('session_duration_seconds', 0),
        'log_level': status.get('log_level', ''),
        'log_sink': status.get('log_sink', ''),
        'failure_reason': status.get('failure_reason', ''),
        'sms_supported': status.get('sms_supported', False),
        'sms_message_count': status.get('sms_message_count', 0),
        'sms_unread_count': status.get('sms_unread_count', 0),
    }


def _raw_hardware(status: dict) -> dict:
    return {
        'manufacturer': status.get('modem_manufacturer', ''),
        'model': status.get('modem_model', ''),
        'imei': status.get('modem_imei', ''),
        'firmware_revision': status.get('modem_firmware', ''),
        'hardware_revision': status.get('modem_hardware_revision', ''),
        'phone_number': status.get('modem_phone_number', ''),
        'phone_numbers': _normalize_list_field(status.get('modem_phone_numbers', [])),
        'device': status.get('modem_device', ''),
        'power_state': status.get('modem_power_state_name', ''),
    }


def _raw_sim(status: dict) -> dict:
    result = {
        'active_slot': status.get('active_sim_slot', 0),
        'configured_slot': status.get('configured_sim_slot', 0),
        'on_configured_sim': status.get('is_on_configured_sim', False),
        'on_failover_sim': status.get('is_on_failover_sim', False),
        'failover_enabled': status.get('sim_failover_enabled', False),
        'failback_enabled': status.get('sim_failback_enabled', True),
        'switch_reason': status.get('sim_switch_reason', ''),
        'imsi': status.get('sim_imsi', ''),
        'iccid': status.get('sim_iccid', ''),
        'operator': status.get('sim_operator', ''),
        'spn': status.get('sim_spn', ''),
        'mcc_mnc': status.get('sim_mcc_mnc', ''),
        'pin_unlock_attempted': status.get('pin_unlock_attempted', False),
        'pin_unlock_failed': status.get('pin_unlock_failed', False),
        'puk_unlock_attempted': status.get('puk_unlock_attempted', False),
        'puk_unlock_failed': status.get('puk_unlock_failed', False),
        'permanently_locked': status.get('sim_permanently_locked', False),
        'pin_retries_remaining': status.get('pin_retries_remaining', ''),
        'puk_retries_remaining': status.get('puk_retries_remaining', ''),
    }
    slots = []
    for n in range(1, 5):
        prefix = f'sim_slot_{n}_'
        if f'{prefix}present' in status:
            slots.append({
                'slot': n,
                'present': status.get(f'{prefix}present', False),
                'enabled': status.get(f'{prefix}enabled', False),
                'imsi': status.get(f'{prefix}imsi', ''),
                'iccid': status.get(f'{prefix}iccid', ''),
                'operator': status.get(f'{prefix}operator', ''),
            })
    if slots:
        result['slots'] = slots
    return result


def _raw_signal(status: dict) -> dict:
    return {
        'percent': status.get('signal_percent', 0),
        'dbm': status.get('signal_dbm', 0),
        'technology': status.get('signal_technology', ''),
        'rssi': status.get('signal_rssi', ''),
        'rsrp': status.get('signal_rsrp', ''),
        'rsrq': status.get('signal_rsrq', ''),
        'snr': status.get('signal_snr', ''),
        'ecio': status.get('signal_ecio', ''),
        'rscp': status.get('signal_rscp', ''),
        'serving_band': status.get('serving_band', ''),
        'serving_earfcn': status.get('serving_earfcn', ''),
        'serving_cell_id': status.get('serving_cell_id', ''),
        'serving_tac': status.get('serving_tac', ''),
        'serving_physical_ci': status.get('serving_physical_ci', ''),
        'serving_cell_type': status.get('serving_cell_type', ''),
        'current_bands': _normalize_list_field(status.get('current_bands', [])),
        'configured_bands': _normalize_list_field(status.get('configured_bands', [])),
    }


# ── Formatters (return human-readable strings) ──────────────────────────

def _kv(label: str, value, width: int = 24) -> str:
    if value == '' or value is None:
        return ''
    return f'  {label:<{width}} {value}'


def _kv_wrapped(label: str, value: str, width: int = 24) -> list[str]:
    """Render a key/value pair with wrapped continuation lines.

    This avoids very long lines being visually mangled in narrow terminals.
    """
    if value == '' or value is None:
        return []

    text = str(value)
    cols = shutil.get_terminal_size((120, 20)).columns
    available = max(20, cols - (2 + width + 1))
    chunks = textwrap.wrap(text, width=available, break_long_words=False, break_on_hyphens=False)

    if not chunks:
        return []

    lines = [f'  {label:<{width}} {chunks[0]}']
    for chunk in chunks[1:]:
        lines.append(f'  {"":<{width}} {chunk}')
    return lines


def _section(title: str) -> str:
    return f'\n  --- {title} ---'


def _format_status(status: dict, interface: str) -> str:
    d = _raw_status(status)
    lines = [f'WWAN status for {interface}:']
    lines.append(_section('Connection'))
    lines.append(_kv('State:', d['state']))
    lines.append(_kv('Connection mode:', d['connection_mode']))
    lines.append(_kv('Power state:', d['power_state']))
    lines.append(_kv('Access technology:', d['access_technology']))
    lines.append(_kv('Operator:', d['operator']))
    lines.append(_kv('Operator code:', d['operator_code']))
    lines.append(_kv('APN:', d['apn']))
    # Always show the requested vs carrier-negotiated APN so the operator can
    # see exactly what was asked for and what the network activated — even when
    # they match.  When the negotiated value could not be read, show 'unknown'
    # rather than hiding the line.
    if d['requested_apn'] or d['negotiated_apn']:
        lines.append(_kv('Requested APN:', d['requested_apn'] or 'unknown'))
        lines.append(_kv('Negotiated APN:', d['negotiated_apn'] or 'unknown'))
    if d['failure_reason']:
        lines.append(_kv('Failure reason:', d['failure_reason']))
    lines.append(_kv('Log level:', d['log_level']))
    lines.append(_kv('Log sink:', d['log_sink']))

    lines.append(_section('IP Configuration'))
    lines.append(_kv('IPv4 address:', d['ipv4_address']))
    lines.append(_kv('IPv4 gateway:', d['ipv4_gateway']))
    lines.append(_kv('IPv4 DNS:', d['ipv4_dns']))
    lines.append(_kv('IPv6 address:', d['ipv6_address']))
    lines.append(_kv('IPv6 gateway:', d['ipv6_gateway']))
    lines.append(_kv('IPv6 DNS:', d['ipv6_dns']))
    lines.append(_kv('MTU:', d['mtu']))

    lines.append(_section('Signal'))
    lines.append(_kv('Quality:', f"{d['signal_percent']}%"))
    lines.append(_kv('Strength:', f"{d['signal_dbm']} dBm"))
    serving_band = status.get('serving_band', '')
    lines.append(_kv('Serving band:', serving_band or 'unavailable'))
    configured = d.get('configured_bands') or []
    if configured and configured != ['all']:
        lines.extend(_kv_wrapped('Configured bands:', ', '.join(configured)))
    bands = d['current_bands']
    if bands:
        lines.extend(_kv_wrapped('Enabled bands:', ', '.join(bands)))

    lines.append(_section('SMS'))
    lines.append(_kv('SMS supported:', 'yes' if d['sms_supported'] else 'no'))
    if d['sms_supported']:
        lines.append(_kv('Messages:', d['sms_message_count']))
        if d['sms_unread_count']:
            lines.append(_kv('Unread:', d['sms_unread_count']))

    lines.append(_section('Data Usage (session)'))
    lines.append(_kv('RX bytes:', f"{d['session_rx_bytes']:,}"))
    lines.append(_kv('TX bytes:', f"{d['session_tx_bytes']:,}"))
    if d['session_duration']:
        mins, secs = divmod(int(d['session_duration']), 60)
        hours, mins = divmod(mins, 60)
        lines.append(_kv('Duration:', f'{hours}h {mins}m {secs}s'))

    return '\n'.join(line for line in lines if line)


def _format_hardware(status: dict, interface: str) -> str:
    d = _raw_hardware(status)
    lines = [f'WWAN hardware for {interface}:']
    lines.append(_kv('Manufacturer:', d['manufacturer']))
    lines.append(_kv('Model:', d['model']))
    lines.append(_kv('IMEI:', d['imei']))
    lines.append(_kv('Firmware revision:', d['firmware_revision']))
    lines.append(_kv('Hardware revision:', d['hardware_revision']))
    lines.append(_kv('Phone number:', d['phone_number']))
    if len(d.get('phone_numbers', [])) > 1:
        lines.append(_kv('All numbers:', ', '.join(d['phone_numbers'])))
    lines.append(_kv('Device path:', d['device']))
    lines.append(_kv('Power state:', d['power_state']))
    return '\n'.join(line for line in lines if line)


def _format_sim(status: dict, interface: str) -> str:
    d = _raw_sim(status)
    lines = [f'WWAN SIM for {interface}:']
    lines.append(_section('Active SIM'))
    lines.append(_kv('Active slot:', d['active_slot']))
    lines.append(_kv('Configured slot:', d['configured_slot']))
    lines.append(_kv('On configured SIM:', 'yes' if d['on_configured_sim'] else 'no'))
    if d['on_failover_sim']:
        lines.append(_kv('On failover SIM:', 'yes'))
        lines.append(_kv('Switch reason:', d['switch_reason']))
    lines.append(_kv('IMSI:', d['imsi']))
    lines.append(_kv('ICCID:', d['iccid']))
    lines.append(_kv('Operator:', d['operator']))
    lines.append(_kv('SPN:', d['spn']))
    lines.append(_kv('MCC/MNC:', d['mcc_mnc']))

    lines.append(_section('Failover'))
    lines.append(_kv('Failover enabled:', 'yes' if d['failover_enabled'] else 'no'))
    lines.append(_kv('Failback enabled:', 'yes' if d['failback_enabled'] else 'no'))

    lines.append(_section('PIN/PUK Status'))
    if d['permanently_locked']:
        lines.append(_kv('Status:', 'PERMANENTLY LOCKED'))
    elif d['pin_unlock_failed'] or d['puk_unlock_failed']:
        lines.append(_kv('PIN unlock:', 'FAILED' if d['pin_unlock_failed'] else 'ok'))
        lines.append(_kv('PUK unlock:', 'FAILED' if d['puk_unlock_failed'] else 'ok'))
    else:
        lines.append(_kv('Status:', 'ok'))
    lines.append(_kv('PIN retries:', d['pin_retries_remaining']))
    lines.append(_kv('PUK retries:', d['puk_retries_remaining']))

    for slot in d.get('slots', []):
        lines.append(_section(f"Slot {slot['slot']}"))
        lines.append(_kv('Present:', 'yes' if slot['present'] else 'no'))
        lines.append(_kv('Enabled:', 'yes' if slot['enabled'] else 'no'))
        lines.append(_kv('IMSI:', slot['imsi']))
        lines.append(_kv('ICCID:', slot['iccid']))
        lines.append(_kv('Operator:', slot['operator']))

    return '\n'.join(line for line in lines if line)


def _format_signal(status: dict, interface: str) -> str:
    d = _raw_signal(status)
    lines = [f'WWAN signal for {interface}:']
    lines.append(_kv('Quality:', f"{d['percent']}%"))
    lines.append(_kv('Strength:', f"{d['dbm']} dBm"))
    lines.append(_kv('Technology:', d['technology']))

    lines.append(_section('Detailed Metrics'))
    lines.append(_kv('RSSI:', f"{d['rssi']} dBm" if d['rssi'] != '' else ''))
    lines.append(_kv('RSRP:', f"{d['rsrp']} dBm" if d['rsrp'] != '' else ''))
    lines.append(_kv('RSRQ:', f"{d['rsrq']} dB" if d['rsrq'] != '' else ''))
    lines.append(_kv('SNR:', f"{d['snr']} dB" if d['snr'] != '' else ''))
    # 3G-only quality metrics — shown only when the modem reports them
    # (UMTS/HSPA serving cell), so LTE/NR output stays uncluttered.
    lines.append(_kv('RSCP:', f"{d['rscp']} dBm" if d['rscp'] != '' else ''))
    lines.append(_kv('Ec/Io:', f"{d['ecio']} dB" if d['ecio'] != '' else ''))

    # Always render the Serving Cell section with placeholders so the
    # field is discoverable even when ModemManager (< 1.22 with QMI)
    # doesn't surface CellInfo data for the active modem.
    lines.append(_section('Serving Cell'))
    lines.append(_kv('Band:', d['serving_band'] or 'unavailable'))
    cell_type = d.get('serving_cell_type', '') or ''
    label = 'EARFCN:' if cell_type == 'lte' else 'ARFCN:'
    lines.append(_kv(label, d['serving_earfcn'] or 'unavailable'))
    lines.append(_kv('Cell ID:', d['serving_cell_id'] or 'unavailable'))
    lines.append(_kv('PCI:', d['serving_physical_ci'] or 'unavailable'))
    lines.append(_kv('TAC:', d['serving_tac'] or 'unavailable'))

    bands = d['current_bands']
    if bands:
        lines.append(_section('Enabled Bands'))
        for band in bands:
            lines.append(f'  {band}')

    # Configured bands — the operator's `supported-bands` selection.  Shown
    # only when a restriction is set (not the 'all' default) so it is clear
    # the request registered, especially for 5G NR which never appears under
    # Enabled Bands (enforced over QMI, not visible in MM CurrentBands).
    configured = d.get('configured_bands') or []
    if configured and configured != ['all']:
        lines.append(_section('Configured Bands'))
        for band in configured:
            lines.append(f'  {band}')

    return '\n'.join(line for line in lines if line)


def _format_detail(status: dict, interface: str) -> str:
    parts = [
        _format_status(status, interface),
        '',
        _format_hardware(status, interface),
        '',
        _format_sim(status, interface),
        '',
        _format_signal(status, interface),
    ]

    lines = [_section('Cumulative Data Usage')]
    cum = status.get('cumulative_bytes', 0)
    cum_plus = status.get('cumulative_plus_session', 0)
    limit = status.get('data_limit_bytes', 0)
    lines.append(_kv('Cumulative bytes:', f'{cum:,}'))
    lines.append(_kv('Including session:', f'{cum_plus:,}'))
    lines.append(_kv('Billing day:', status.get('data_limit_billing_date', 1)))
    lines.append(_kv('Tracked slot:', status.get('usage_tracking_slot', '')))
    if limit:
        lines.append(_kv('Data limit:', f'{limit:,}'))
        lines.append(_kv('Usage:', f"{status.get('data_usage_percent', 0)}%"))
        lines.append(_kv('Limit action:', status.get('data_limit_action', '')))

    # Show persisted cumulative for every SIM slot we have a record for —
    # including inactive slots whose totals carry over across SIM failovers.
    per_slot = status.get('per_slot_cumulative', {}) or {}
    if isinstance(per_slot, dict) and per_slot:
        def _slot_sort_key(k):
            try:
                return (0, int(k))
            except (TypeError, ValueError):
                return (1, str(k))
        for slot_key in sorted(per_slot.keys(), key=_slot_sort_key):
            entry = per_slot[slot_key] or {}
            slot_num = slot_key
            is_active = entry.get('is_active', False)
            marker = ' (active)' if is_active else ' (inactive)'
            lines.append(_section(f'Slot {slot_num}{marker} Data Usage'))
            slot_cum = entry.get('cumulative_bytes', 0)
            slot_total = entry.get('cumulative_plus_session', slot_cum)
            slot_limit = entry.get('data_limit_bytes', 0)
            lines.append(_kv('Cumulative bytes:', f'{slot_cum:,}'))
            if is_active:
                lines.append(_kv('Including session:', f'{slot_total:,}'))
            lines.append(_kv('Billing day:', entry.get('data_limit_billing_date', 1)))
            if slot_limit:
                lines.append(_kv('Data limit:', f'{slot_limit:,}'))
                lines.append(_kv('Usage:', f"{entry.get('data_usage_percent', 0)}%"))
                lines.append(_kv('Limit action:', entry.get('data_limit_action', '')))
            warnings = entry.get('data_limit_warning') or []
            if warnings:
                lines.append(_kv('Warning thresholds:', ', '.join(f'{w}%' for w in warnings)))
            last_updated = entry.get('last_updated', '')
            if last_updated:
                lines.append(_kv('Last updated:', last_updated))

    lines.append(_section('Failover History'))
    lines.append(_kv('Failover count:', status.get('lifetime_failover_count', 0)))
    lines.append(_kv('Last failover:', status.get('last_failover_time', '')))
    lines.append(_kv('Recovery attempts:', status.get('connectivity_recovery_attempts', 0)))

    lines.append(_section('Runtime Counters'))
    lines.append(_kv('Bearer drops:', status.get('bearer_disconnect_count', 0)))
    lines.append(_kv('Registration losses:', status.get('registration_loss_count', 0)))
    lines.append(_kv('Reconnect attempts:', status.get('reconnect_attempt_count', 0)))
    lines.append(_kv('Reconnect successes:', status.get('reconnect_success_count', 0)))
    lines.append(_kv('SIM switches:', status.get('sim_switch_count', 0)))
    lines.append(_kv('Total downtime:', f"{status.get('total_bearer_downtime_seconds', 0)}s"))
    current_down = status.get('current_bearer_downtime_seconds', 0)
    if current_down:
        lines.append(_kv('Current downtime:', f'{current_down}s'))
    lines.append(_kv('Last disconnect:', status.get('last_disconnect_time', '')))
    lines.append(_kv('Last reason:', status.get('last_disconnect_reason', '')))

    lines.append(_section('Diagnostics (since power on)'))
    lines.append(_kv('Service starts:', status.get('service_start_count', 0)))
    lines.append(_kv('ModemManager restarts:', status.get('modemmanager_restart_count', 0)))
    lines.append(_kv('Modem hardware resets:', status.get('hardware_reset_count', 0)))
    lines.append(_kv('Modem nuclear resets:', status.get('modem_nuclear_reset_count', 0)))

    lines.append(_section('Configuration'))
    lines.append(_kv('Network mode:', status.get('network_mode', '')))
    lines.append(_kv('Reconnection:', status.get('enhanced_reconnection', '')))
    lines.append(_kv('Monitoring:', status.get('connectivity_monitoring', '')))
    lines.append(_kv('Interface mgmt:', status.get('interface_management', '')))
    lines.append(_kv('Log level:', status.get('log_level', '')))
    lines.append(_kv('Log sink:', status.get('log_sink', '')))
    lines.append(_kv('Verbose logging:', status.get('verbose_logging', '')))

    parts.append('\n'.join(line for line in lines if line))
    return '\n'.join(parts)


def _format_alert(alert: dict, interface: str) -> str:
    lines = [f'WWAN alert for {interface}:']
    lines.append(_kv('Sequence:', alert.get('sequence', '')))
    lines.append(_kv('Timestamp:', alert.get('timestamp', '')))
    lines.append(_kv('Type:', alert.get('type', '')))
    lines.append(_kv('Severity:', alert.get('severity', '')))
    lines.append(_kv('Source:', alert.get('source', '')))
    lines.append(_kv('FSM state:', alert.get('fsm_state', '')))
    lines.extend(_kv_wrapped('Message:', str(alert.get('message', ''))))

    details = alert.get('details')
    if details:
        if isinstance(details, dict):
            details_text = ', '.join(f'{k}={v}' for k, v in details.items())
        else:
            details_text = str(details)
        lines.extend(_kv_wrapped('Details:', details_text))

    return '\n'.join(line for line in lines if line)


# ── Public op-mode entry points ─────────────────────────────────────────

def show_status(raw: bool, interface: str):
    status = _get_full_status(interface)
    if raw:
        return _raw_status(status)
    return _format_status(status, interface)


def show_hardware(raw: bool, interface: str):
    status = _get_full_status(interface)
    if raw:
        return _raw_hardware(status)
    return _format_hardware(status, interface)


def show_sim(raw: bool, interface: str):
    status = _get_full_status(interface)
    if raw:
        return _raw_sim(status)
    return _format_sim(status, interface)


def show_signal(raw: bool, interface: str):
    status = _get_full_status(interface)
    if raw:
        return _raw_signal(status)
    return _format_signal(status, interface)


def show_detail(raw: bool, interface: str):
    status = _get_full_status(interface)
    if raw:
        return status
    return _format_detail(status, interface)


def show_wait_failover(raw: bool,
                       interface: str,
                       timeout: int = 120,
                       poll_interval: int = 1,
                       include_existing: bool = False):
    """Wait for next failover alert for an interface and print it.

    This consumes WWANClientSync.wait_for_failover_alert() directly so
    operators can do a quick interactive wait in op-mode.
    """
    try:
        timeout = int(timeout)
    except (TypeError, ValueError):
        raise ValueError('Timeout must be an integer (1-600 seconds)')

    try:
        poll_interval = int(poll_interval)
    except (TypeError, ValueError):
        raise ValueError('Poll interval must be an integer (>= 1 second)')

    if timeout < 1 or timeout > 600:
        raise ValueError('Timeout must be between 1 and 600 seconds')
    if poll_interval < 1:
        raise ValueError('Poll interval must be >= 1 second')

    config = ConfigTreeQuery()
    if not config.exists(['interfaces', 'wwan', interface]):
        raise vyos.opmode.UnconfiguredSubsystem(
            f'Interface "{interface}" is not configured'
        )

    if_num = _get_interface_number(interface)
    try:
        client = _get_client()
        alert = client.wait_for_failover_alert(
            interface_number=if_num,
            timeout=float(timeout),
            poll_interval=float(poll_interval),
            include_existing=include_existing,
        )
    except Exception as e:
        raise vyos.opmode.DataUnavailable(
            f'Cannot wait for WWAN failover alert on {interface}: {e}'
        )

    if not alert:
        return (
            f'No failover alert observed for {interface} '
            f'within {timeout}s'
        )

    if raw:
        return alert
    return _format_alert(alert, interface)


def show_monitor_alerts(raw: bool,
                        interface: str,
                        timeout: int = 30,
                        severity: str = '',
                        category: str = ''):
    """Collect and display WWAN alerts for a fixed monitoring window."""
    try:
        timeout = int(timeout)
    except (TypeError, ValueError):
        raise ValueError('Timeout must be an integer (1-600 seconds)')

    if timeout < 1 or timeout > 600:
        raise ValueError('Timeout must be between 1 and 600 seconds')

    severity = str(severity or '').strip().lower()
    category = str(category or '').strip().lower()

    if severity and severity not in ('info', 'warning', 'critical'):
        raise ValueError('Severity must be one of: info, warning, critical')

    if category and category not in ('connectivity', 'sim', 'usage'):
        raise ValueError('Category must be one of: connectivity, sim, usage')

    config = ConfigTreeQuery()
    if not config.exists(['interfaces', 'wwan', interface]):
        raise vyos.opmode.UnconfiguredSubsystem(
            f'Interface "{interface}" is not configured'
        )

    if_num = _get_interface_number(interface)
    try:
        client = _get_client()
        alerts = client.monitor_alerts(
            timeout=float(timeout),
            interface_number=if_num,
            severity=severity or None,
            category=category or None,
            include_existing=False,
        )
    except Exception as e:
        raise vyos.opmode.DataUnavailable(
            f'Cannot monitor WWAN alerts on {interface}: {e}'
        )

    if raw:
        return alerts

    lines = [
        f'WWAN alert monitor for {interface}: {len(alerts)} alert(s) captured in {timeout}s'
    ]
    if severity:
        lines.append(_kv('Severity filter:', severity))
    if category:
        lines.append(_kv('Category filter:', category))

    if not alerts:
        lines.append('  (no alerts observed)')
        return '\n'.join(lines)

    for idx, alert in enumerate(alerts, start=1):
        lines.append(_section(f'Alert {idx}'))
        lines.append(_kv('Sequence:', alert.get('sequence', '')))
        lines.append(_kv('Timestamp:', alert.get('timestamp', '')))
        lines.append(_kv('Code:', alert.get('code', '')))
        lines.append(_kv('Type:', alert.get('type', '')))
        lines.append(_kv('Category:', alert.get('category', '')))
        lines.append(_kv('Severity:', alert.get('severity', '')))
        lines.extend(_kv_wrapped('Message:', str(alert.get('message', ''))))

    return '\n'.join(line for line in lines if line)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
