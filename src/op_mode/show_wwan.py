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
        'current_bands': _normalize_list_field(status.get('current_bands', [])),
    }


# ── Formatters (return human-readable strings) ──────────────────────────

def _kv(label: str, value, width: int = 24) -> str:
    if value == '' or value is None:
        return ''
    return f'  {label:<{width}} {value}'


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
    bands = d['current_bands']
    if bands:
        lines.append(_kv('Active bands:', ', '.join(bands)))

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

    bands = d['current_bands']
    if bands:
        lines.append(_section('Active Bands'))
        for band in bands:
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
    if limit:
        lines.append(_kv('Data limit:', f'{limit:,}'))
        lines.append(_kv('Usage:', f"{status.get('data_usage_percent', 0)}%"))
        lines.append(_kv('Limit action:', status.get('data_limit_action', '')))

    lines.append(_section('Failover History'))
    lines.append(_kv('Failover count:', status.get('failover_count', 0)))
    lines.append(_kv('Last failover:', status.get('last_failover_time', '')))
    lines.append(_kv('Recovery attempts:', status.get('connectivity_recovery_attempts', 0)))

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


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
