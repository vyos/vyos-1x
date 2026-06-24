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

from __future__ import annotations

import asyncio
import datetime
import json
import os
import uuid
from dbus_next import Variant  # pylint: disable=import-error
from dbus_next.service import ServiceInterface, method, signal  # pylint: disable=import-error
from dbus_next.errors import DBusError  # pylint: disable=import-error
from vyos.utils.wwan.interfaces_wwan_state_machine import ModemStateMachine
from vyos.utils.wwan.interfaces_wwan_config import InterfaceConfig
from vyos.utils.wwan.wwan_logging import setup_logging


logger = setup_logging(__name__, "wwan-service")

try:
    from systemd import journal  # pylint: disable=import-error
    JOURNAL_AVAILABLE = True
except Exception:
    journal = None
    JOURNAL_AVAILABLE = False


def _python_to_variant(value):
    """Recursively convert Python values to dbus_next Variant values."""
    if isinstance(value, dict):
        return Variant('a{sv}', {k: _python_to_variant(v) for k, v in value.items()})
    if isinstance(value, list):
        if not value:
            return Variant('as', [])
        if all(isinstance(x, str) for x in value):
            return Variant('as', value)
        if all(isinstance(x, bool) for x in value):
            return Variant('ab', value)
        if all(isinstance(x, int) and not isinstance(x, bool) for x in value):
            return Variant('ax', value)
        if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in value):
            return Variant('ad', [float(x) for x in value])
        return Variant('av', [_python_to_variant(x) for x in value])
    if isinstance(value, bool):
        return Variant('b', value)
    if isinstance(value, int):
        return Variant('x', value)
    if isinstance(value, float):
        return Variant('d', value)
    if isinstance(value, str):
        return Variant('s', value)
    return Variant('s', str(value))


def _to_dbus_alert(alert):
    """Convert an alert dict into an a{sv} payload."""
    return {k: _python_to_variant(v) for k, v in alert.items()}


class AlertBusInterface(ServiceInterface):
    """Generalized alert bus for WWAN consumers (SNMP/REST/MQTT/etc.)."""

    def __init__(self, manager):
        super().__init__("com.igos.IgosModemManager.AlertBus")
        self.manager = manager

    @signal()
    def Alert(self, payload: 'a{sv}') -> 'a{sv}':  # type: ignore[name-defined]  # noqa: F821, F722
        """Broadcast a normalized alert envelope."""
        return payload

    @signal()
    def AlertRaised(self, alert_json: 's') -> 's':  # type: ignore[name-defined]  # noqa: F821, F722
        """Compatibility signal carrying alert envelope as JSON string."""
        return alert_json

    def emit_alert(self, alert):
        """Emit Alert signal for a normalized alert dict."""
        self.Alert(_to_dbus_alert(alert))
        self.AlertRaised(json.dumps(alert, separators=(',', ':')))

    @method()
    def GetRecentAlerts(self, limit: 'i', interface_number: 'i') -> 'aa{sv}':  # type: ignore[name-defined]  # noqa: F821, F722
        """Return recent alerts, optionally filtered by interface.

        Args:
            limit: max alerts to return (<=0 means manager default)
            interface_number: interface index filter; -1 means all interfaces
        """
        alerts = self.manager.get_recent_alerts(limit, interface_number)
        return [_to_dbus_alert(a) for a in alerts]

    @method()
    def ClearAlerts(self, interface_number: 'i') -> 's':  # type: ignore[name-defined]  # noqa: F821
        """Clear alert history globally (-1) or for one interface."""
        cleared = self.manager.clear_alerts(interface_number)
        return f"Cleared {cleared} alert(s)"

    @method()
    def AckAlert(self, alert_id: 's') -> 'b':  # type: ignore[name-defined]  # noqa: F821
        """Mark a specific alert as acknowledged by alert id."""
        return self.manager.ack_alert(alert_id)

class ControlInterface(ServiceInterface):
    """
    Exposed at /com/igos/IgosModemManager/Control
    Allows external clients to dynamically create/delete and export
    a new InterfaceN object.
    """
    def __init__(self, manager):
        super().__init__("com.igos.IgosModemManager.Control")
        self.manager = manager

    @method()
    async def AddInterface(self, interface_number: 'i') -> 's':  # type: ignore[name-defined]  # noqa: F821
        try:
            logger.info("Adding interface", extra={'interface_number': interface_number})
            await self.manager.add_interface(interface_number)
            logger.info("Interface added successfully", extra={'interface_number': interface_number})
            return f"Interface {interface_number} ready"
        except Exception as e:
            logger.error(f"Failed to add interface: {e}", extra={'interface_number': interface_number})
            raise DBusError("com.igos.IgosModemManager.Error", str(e))

    @method()
    async def RemoveInterface(self, interface_number: 'i') -> 's':  # type: ignore[name-defined]  # noqa: F821
        try:
            logger.info("Removing interface", extra={'interface_number': interface_number})
            await self.manager.remove_interface(interface_number)
            logger.info("Interface removed successfully", extra={'interface_number': interface_number})
            return f"Interface {interface_number} removed"
        except Exception as e:
            logger.error(f"Failed to remove interface: {e}", extra={'interface_number': interface_number})
            raise DBusError("com.igos.IgosModemManager.Error", str(e))

class ConfigServiceManager:
    def __init__(self, bus):
        self.interface_objects = {}        # interface_number -> InterfaceConfig
        self.modem_state_machines = {}     # interface_number -> ModemStateMachine
        self.bus = bus
        self._alert_sequence = 0
        self.max_alert_history = 500
        self.alert_history = []
        self.control_interface = None
        self.alert_interface = None
        # Serialize reconnection/re-export cycles. NameOwnerChanged and
        # watchdog recovery can overlap; without a lock we can double-export
        # paths on the same bus and/or race bus disconnects.
        self._bus_update_lock = asyncio.Lock()

    _ALERT_TYPE_MAP = {
        'bearer_down': ('connectivity', 'WWAN_BEARER_DOWN'),
        'bearer_up': ('connectivity', 'WWAN_BEARER_UP'),
        'reconnect_attempt': ('connectivity', 'WWAN_RECONNECT_ATTEMPT'),
        'sim_failover': ('sim', 'WWAN_SIM_FAILOVER'),
        'sim_switch': ('sim', 'WWAN_SIM_SWITCH'),
        'fsm_failed': ('connectivity', 'WWAN_FSM_FAILED'),
        'usage_warning': ('usage', 'WWAN_USAGE_WARNING'),
        'usage_limit_exceeded': ('usage', 'WWAN_USAGE_LIMIT_EXCEEDED'),
    }

    _ALLOWED_STATES = {'open', 'cleared', 'acked'}
    _ALLOWED_SEVERITIES = {'info', 'warning', 'critical'}

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')

    @classmethod
    def _normalize_severity(cls, value) -> str:
        raw = str(value or 'info').strip().lower()
        if raw in ('error', 'err', 'critical', 'crit'):
            return 'critical'
        if raw in ('warn', 'warning'):
            return 'warning'
        if raw in cls._ALLOWED_SEVERITIES:
            return raw
        return 'info'

    def _emit_alert_to_journal(self, alert):
        """Bridge normalized alerts into journald for service event-handler rules."""
        if not JOURNAL_AVAILABLE:
            return

        try:
            msg = str(alert.get('message', 'WWAN alert'))
            alert_json = json.dumps(alert, separators=(',', ':'), sort_keys=True)
            _severity_priority = {'critical': 3, 'warning': 4, 'info': 6}
            priority = _severity_priority.get(str(alert.get('severity', 'info')), 6)
            journal.send(
                msg,
                PRIORITY=str(priority),
                SYSLOG_IDENTIFIER='igos-wwan-alertbus',
                WWAN_ALERT='1',
                WWAN_ALERT_SEQUENCE=str(alert.get('sequence', '')),
                WWAN_ALERT_TIMESTAMP=str(alert.get('timestamp', '')),
                WWAN_ALERT_SOURCE=str(alert.get('source', 'wwan-fsm')),
                WWAN_ALERT_TYPE=str(alert.get('type', 'event')),
                WWAN_ALERT_CODE=str(alert.get('code', 'WWAN_EVENT')),
                WWAN_ALERT_CATEGORY=str(alert.get('category', 'connectivity')),
                WWAN_ALERT_STATE=str(alert.get('state', 'open')),
                WWAN_ALERT_ID=str(alert.get('id', '')),
                WWAN_ALERT_SEVERITY=str(alert.get('severity', 'info')),
                WWAN_ALERT_INTERFACE=str(alert.get('interface_number', -1)),
                WWAN_ALERT_FSM_STATE=str(alert.get('fsm_state', '')),
                WWAN_ALERT_MESSAGE=msg,
            )

            # Optional JSON stream for event-handler scripts that need a
            # machine-friendly payload (e.g. HTTPS webhook body).
            journal.send(
                alert_json,
                PRIORITY=str(priority),
                SYSLOG_IDENTIFIER='igos-wwan-alertbus-json',
                WWAN_ALERT='1',
                WWAN_ALERT_JSON='1',
                WWAN_ALERT_SEQUENCE=str(alert.get('sequence', '')),
                WWAN_ALERT_ID=str(alert.get('id', '')),
                WWAN_ALERT_INTERFACE=str(alert.get('interface_number', -1)),
            )
        except Exception as e:
            logger.debug(f"Failed to bridge alert to journal: {e}")

    def _normalize_alert(self, alert):
        """Normalize arbitrary alert payloads into a stable envelope."""
        now = self._utc_now_iso()
        base = {
            'id': '',
            'timestamp': now,
            'sequence': 0,
            'source': 'wwan-fsm',
            'type': 'event',
            'code': 'WWAN_EVENT',
            'category': 'connectivity',
            'severity': 'info',
            'message': '',
            'interface_number': -1,
            'labels': {},
            'state': 'open',
            'dedupe_key': '',
        }
        if isinstance(alert, dict):
            base.update(alert)
        elif alert is not None:
            base['message'] = str(alert)

        self._alert_sequence += 1
        base['sequence'] = self._alert_sequence

        try:
            base['interface_number'] = int(base.get('interface_number', -1))
        except (TypeError, ValueError):
            base['interface_number'] = -1

        # Derive stable category/code from the alert `type` when the
        # caller did not supply an explicit code/category pair.
        if not base.get('code') or not base.get('category'):
            mapped = self._ALERT_TYPE_MAP.get(str(base.get('type', 'event')).lower())
            if mapped:
                category, code = mapped
                base['category'] = base.get('category') or category
                base['code'] = base.get('code') or code

        # Fallbacks if still missing
        if not base.get('category'):
            base['category'] = 'connectivity'
        if not base.get('code'):
            base['code'] = 'WWAN_EVENT'

        base['severity'] = self._normalize_severity(base.get('severity'))

        state = str(base.get('state', 'open')).lower()
        base['state'] = state if state in self._ALLOWED_STATES else 'open'

        labels = base.get('labels')
        if not isinstance(labels, dict):
            labels = {}
        labels.setdefault('interface', str(base.get('interface_number', -1)))
        labels.setdefault('fsm_state', str(base.get('fsm_state', '')))
        labels.setdefault('type', str(base.get('type', 'event')))
        base['labels'] = labels

        if not base.get('id'):
            base['id'] = str(uuid.uuid4())

        if not base.get('dedupe_key'):
            base['dedupe_key'] = (
                f"{base.get('code')}|{base.get('source')}|"
                f"{base.get('interface_number')}|{base.get('state')}"
            )

        if not base.get('timestamp'):
            base['timestamp'] = now

        return base

    def emit_alert(self, alert):
        """Append to ring buffer and emit Alert signal."""
        normalized = self._normalize_alert(alert)
        self.alert_history.append(normalized)
        if len(self.alert_history) > self.max_alert_history:
            self.alert_history = self.alert_history[-self.max_alert_history:]

        self._emit_alert_to_journal(normalized)

        logger.info("Alert emitted",
                   extra={'sequence': normalized.get('sequence'),
                          'type': normalized.get('type'),
                          'severity': normalized.get('severity'),
                          'interface_number': normalized.get('interface_number')})

        if self.alert_interface:
            try:
                self.alert_interface.emit_alert(normalized)
            except Exception as e:
                logger.error(f"Failed to emit alert signal: {e}")

    def get_recent_alerts(self, limit, interface_number):
        """Return recent alerts with optional interface filter."""
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 50
        if limit <= 0:
            limit = 50

        filtered = self.alert_history
        if interface_number is not None and int(interface_number) >= 0:
            filtered = [a for a in filtered if a.get('interface_number') == int(interface_number)]

        return filtered[-limit:]

    def clear_alerts(self, interface_number):
        """Clear all alerts or only alerts for one interface.

        Returns the number of alerts removed.
        """
        if interface_number is None or int(interface_number) < 0:
            cleared = len(self.alert_history)
            self.alert_history = []
            return cleared

        target = int(interface_number)
        before = len(self.alert_history)
        self.alert_history = [a for a in self.alert_history if a.get('interface_number') != target]
        return before - len(self.alert_history)

    def ack_alert(self, alert_id):
        """Mark an alert as acknowledged by id.

        Returns True when an alert with this id exists (already acked or newly
        transitioned to acked), otherwise False.
        """
        if not alert_id:
            return False

        for alert in reversed(self.alert_history):
            if str(alert.get('id', '')) != str(alert_id):
                continue
            if str(alert.get('state', 'open')).lower() != 'acked':
                alert['state'] = 'acked'
                alert['acked_timestamp'] = self._utc_now_iso()
            return True
        return False

    async def run(self, initial_interface=None):
        await self.bus.request_name("com.igos.IgosModemManager")
        self.control_interface = ControlInterface(self)
        self.alert_interface = AlertBusInterface(self)

        self.bus.export("/com/igos/IgosModemManager/Control", self.control_interface)
        self.bus.export("/com/igos/IgosModemManager/AlertBus", self.alert_interface)

        # Auto-create initial interface if specified (non-on-demand mode)
        if initial_interface is not None:
            logger.info(f"Auto-creating interface {initial_interface} for immediate connection")
            await self.add_interface(initial_interface)
        else:
            logger.info("WWAN ConfigService is running, waiting for AddInterface() calls")

        await asyncio.get_event_loop().create_future()

    async def add_interface(self, interface_number: int):
        object_path = f"/com/igos/IgosModemManager/Interface{interface_number}"

        # Idempotency: AddInterface is called on every config apply. If the
        # interface object is already exported, do not recreate InterfaceConfig
        # (which would re-run restore logic and can race with SetConfiguration).
        if interface_number in self.interface_objects:
            logger.info("Interface already exists, reusing exported object",
                       extra={'interface_number': interface_number,
                              'object_path': object_path})
            return

        fsm = self.modem_state_machines.get(interface_number)
        if fsm is None:
            logger.info("Creating new state machine",
                       extra={'interface_number': interface_number})

            # Create FSM without configuration - will be set via D-Bus SetConfiguration
            fsm = ModemStateMachine(interface_number, self.bus, alert_emitter=self.emit_alert)
            logger.info("State machine created without configuration - awaiting D-Bus SetConfiguration",
                       extra={'interface_number': interface_number})

            await fsm.initialize()

            self.modem_state_machines[interface_number] = fsm

        iface = InterfaceConfig(interface_number, fsm)
        self.bus.export(object_path, iface)
        self.interface_objects[interface_number] = iface

        logger.info("Interface exported",
                   extra={'interface_number': interface_number, 'object_path': object_path})

    async def remove_interface(self, interface_number: int):
        object_path = f"/com/igos/IgosModemManager/Interface{interface_number}"

        # Clean up configuration persistence file first
        config_iface = self.interface_objects.get(interface_number)
        if config_iface:
            try:
                config_iface._remove_configuration()
            except Exception as e:
                logger.error(f"Error removing configuration file during removal: {e}",
                           extra={'interface_number': interface_number})

        # Fallback cache cleanup if InterfaceConfig object is already gone.
        # Keeps delete semantics strong even after partial service failures.
        cache_file = f"/run/wwan/interface{interface_number}.conf"
        for path in (cache_file, cache_file + '.bad'):
            try:
                if os.path.exists(path):
                    os.remove(path)
                    logger.info("Removed interface cache file",
                               extra={'interface_number': interface_number,
                                      'cache_file': path})
            except Exception as e:
                logger.error(f"Error removing cache file during removal: {e}",
                           extra={'interface_number': interface_number,
                                  'cache_file': path})

        # Shutdown FSM gracefully
        fsm = self.modem_state_machines.get(interface_number)
        if fsm:
            try:
                await fsm.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down FSM during removal: {e}",
                           extra={'interface_number': interface_number})

        # Unexport the D-Bus object
        self.bus.unexport(object_path)

        # Remove from internal dictionaries
        self.interface_objects.pop(interface_number, None)
        self.modem_state_machines.pop(interface_number, None)

        logger.info("Interface removed",
                   extra={'interface_number': interface_number, 'object_path': object_path})

    async def update_bus_connection(self, new_bus):
        """Update the D-Bus connection after ModemManager restart"""
        async with self._bus_update_lock:
            try:
                logger.info("Updating D-Bus connection after ModemManager restart",
                           extra={'fsm_count': len(self.modem_state_machines)})

                # Update the bus reference
                old_bus = self.bus
                self.bus = new_bus

                # Ensure service name ownership on the current bus
                await self.bus.request_name("com.igos.IgosModemManager")

                # Best-effort cleanup before re-export in case this callback
                # runs multiple times against the same bus object.
                try:
                    self.bus.unexport("/com/igos/IgosModemManager/Control")
                except Exception:
                    pass
                try:
                    self.bus.unexport("/com/igos/IgosModemManager/AlertBus")
                except Exception:
                    pass
                for interface_number in self.interface_objects:
                    object_path = f"/com/igos/IgosModemManager/Interface{interface_number}"
                    try:
                        self.bus.unexport(object_path)
                    except Exception:
                        pass

                # Re-export the control interface
                self.control_interface = ControlInterface(self)
                self.alert_interface = AlertBusInterface(self)
                self.bus.export("/com/igos/IgosModemManager/Control", self.control_interface)
                self.bus.export("/com/igos/IgosModemManager/AlertBus", self.alert_interface)

                # Re-export any existing interface objects
                for interface_number, iface in self.interface_objects.items():
                    object_path = f"/com/igos/IgosModemManager/Interface{interface_number}"
                    self.bus.export(object_path, iface)
                    logger.info("Re-exported interface",
                               extra={'interface_number': interface_number, 'object_path': object_path})

                # Update FSM bus connections
                for interface_number, fsm in self.modem_state_machines.items():
                    try:
                        await fsm.update_bus_connection(new_bus)
                    except Exception as e:
                        logger.error(f"Failed to update FSM bus connection: {e}",
                                   extra={'interface_number': interface_number})

                # Disconnect old bus only when we actually switched objects.
                # If old_bus == new_bus, disconnecting here would tear down the
                # active connection and make the control interface disappear.
                if old_bus and old_bus is not self.bus:
                    old_bus.disconnect()

                logger.info("D-Bus connection updated successfully",
                           extra={'fsm_count': len(self.modem_state_machines)})

            except Exception as e:
                logger.error(f"Failed to update D-Bus connection: {e}")
                raise

    async def shutdown(self):
        """Graceful shutdown of the service manager"""
        logger.info("Shutting down ConfigServiceManager",
                   extra={'fsm_count': len(self.modem_state_machines)})

        # Stop all FSMs
        for interface_number, fsm in self.modem_state_machines.items():
            try:
                await fsm.shutdown()
                logger.info("FSM shutdown complete", extra={'interface_number': interface_number})
            except Exception as e:
                logger.error(f"Error shutting down FSM: {e}",
                           extra={'interface_number': interface_number})

        # Clear references
        self.interface_objects.clear()
        self.modem_state_machines.clear()

        logger.info("ConfigServiceManager shutdown complete")
