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

import sys

import vyos.opmode

from vyos.configquery import ConfigTreeQuery


def _get_interface_number(interface: str) -> int:
    """Extract numeric index from interface name (e.g. 'wwan0' -> 0)."""
    return int(interface.replace('wwan', ''))


def _get_client():
    """Return a WWANClientSync instance."""
    from vyos.utils.wwan.wwan_client import WWANClientSync
    return WWANClientSync()


def _check_interface(interface: str):
    """Verify the interface is configured."""
    config = ConfigTreeQuery()
    if not config.exists(['interfaces', 'wwan', interface]):
        raise vyos.opmode.UnconfiguredSubsystem(
            f'Interface "{interface}" is not configured'
        )


# ── Formatters ──────────────────────────────────────────────────────────

def _kv(label: str, value, width: int = 18) -> str:
    if value == '' or value is None:
        return ''
    return f'  {label:<{width}} {value}'


def _format_message_summary(msg: dict) -> str:
    """One-line summary for list view."""
    msg_id = msg.get('id', '?')
    direction = msg.get('direction', '?')
    number = msg.get('number', '?')
    timestamp = msg.get('timestamp', '')
    text = str(msg.get('text', ''))
    read_flag = ''
    if direction == 'incoming' and not msg.get('read', False):
        read_flag = ' [NEW]'

    # Truncate text for list view
    if len(text) > 50:
        text = text[:47] + '...'

    arrow = '<-' if direction == 'incoming' else '->'
    return f'  {msg_id:>4}  {arrow} {number:<16} {timestamp[:19]:<20} {text}{read_flag}'


def _format_message_detail(msg: dict) -> str:
    """Full message display."""
    lines = []
    lines.append(_kv('ID:', msg.get('id', '')))
    lines.append(_kv('Direction:', msg.get('direction', '')))
    lines.append(_kv('Number:', msg.get('number', '')))
    lines.append(_kv('Timestamp:', msg.get('timestamp', '')))
    lines.append(_kv('Status:', msg.get('status', '')))
    if msg.get('direction') == 'incoming':
        lines.append(_kv('Read:', 'yes' if msg.get('read', False) else 'no'))
    lines.append('')
    lines.append(f'  {msg.get("text", "")}')
    return '\n'.join(line for line in lines if line is not None)


# ── Public op-mode entry points ─────────────────────────────────────────

def send_sms(raw: bool, interface: str, number: str, message: str):
    """Send an SMS message.

    CLI: send sms interface <wwan0> number <phone> message <text>
    """
    _check_interface(interface)
    if_num = _get_interface_number(interface)
    try:
        client = _get_client()
        result = client.send_sms(if_num, number, message)
    except Exception as e:
        raise vyos.opmode.DataUnavailable(
            f'Cannot send SMS via {interface}: {e}'
        )
    if raw:
        return result
    return f"SMS sent to {number} (message id: {result.get('message_id', '?')})"


def show_sms(raw: bool, interface: str):
    """List all SMS messages.

    CLI: show interfaces wwan <wwan0> sms
    """
    _check_interface(interface)
    if_num = _get_interface_number(interface)
    try:
        client = _get_client()
        messages = client.list_sms(if_num)
    except Exception as e:
        raise vyos.opmode.DataUnavailable(
            f'Cannot retrieve SMS for {interface}: {e}'
        )
    if raw:
        return messages

    if not messages:
        return f'No SMS messages for {interface}'

    lines = [f'SMS messages for {interface}:']
    lines.append(f'  {"ID":>4}  {"":2} {"Number":<16} {"Timestamp":<20} Message')
    lines.append(f'  {"----":>4}  {"--":2} {"----------------":<16} {"-------------------":<20} -------')
    for msg in messages:
        lines.append(_format_message_summary(msg))
    lines.append(f'\n  Total: {len(messages)} message(s)')
    return '\n'.join(lines)


def show_sms_message(raw: bool, interface: str, message_id: int):
    """Show a specific SMS message.

    CLI: show interfaces wwan <wwan0> sms <id> or sms message <id>
    """
    _check_interface(interface)
    if_num = _get_interface_number(interface)
    try:
        client = _get_client()
        msg = client.read_sms(if_num, message_id)
    except Exception as e:
        raise vyos.opmode.DataUnavailable(
            f'Cannot read SMS {message_id} on {interface}: {e}'
        )
    if raw:
        return msg
    return _format_message_detail(msg)


def delete_sms(raw: bool, interface: str, message_id: int):
    """Delete a specific SMS message.

    CLI: delete interfaces wwan <wwan0> sms message <id>
    """
    _check_interface(interface)
    if_num = _get_interface_number(interface)
    try:
        client = _get_client()
        result = client.delete_sms(if_num, message_id)
    except Exception as e:
        raise vyos.opmode.DataUnavailable(
            f'Cannot delete SMS {message_id} on {interface}: {e}'
        )
    if raw:
        return result
    return f"SMS message {message_id} deleted"


def delete_all_sms(raw: bool, interface: str):
    """Delete all SMS messages.

    CLI: delete interfaces wwan <wwan0> sms
    """
    _check_interface(interface)
    if_num = _get_interface_number(interface)
    try:
        client = _get_client()
        result = client.delete_all_sms(if_num)
    except Exception as e:
        raise vyos.opmode.DataUnavailable(
            f'Cannot delete SMS on {interface}: {e}'
        )
    if raw:
        return result
    return "All SMS messages deleted"


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
