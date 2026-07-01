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

"""AlertBus subscriber adapters for protocol fan-out (REST/MQTT/SNMP).

This module intentionally keeps protocol integrations decoupled from WWAN FSM
core logic.  Adapters subscribe to AlertBus through ``WWANClient`` and translate
normalized alert envelopes to protocol-specific payloads.

Design goals:
- Keep WWAN core stable while adapter implementations evolve independently.
- Provide a minimal skeleton that can be composed by services/daemons.
- Avoid hard dependency on optional protocol libraries where possible.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections import deque
from typing import Any, Callable, Deque, Dict, Optional

from vyos.utils.wwan.wwan_client import WWANClient

logger = logging.getLogger(__name__)


# Stable machine code → SNMP NOTIFICATION-TYPE OID mapping.
# These map to NOTIFICATION-TYPEs in IGOS-WWAN-MIB under
# igosWwanNotifications.0 ({ enterprises 44641 }.1.2.0.N).
# Keep in sync with mibs/IGOS-WWAN-MIB.txt and
# python/vyos/utils/wwan/snmp_traps.py::TRAP_MAP.
ALERT_CODE_TO_SNMP_OID = {
    # igosWwanFsmStateChange      (.1)
    'WWAN_FSM_FAILED':            '1.3.6.1.4.1.44641.1.2.0.1',
    'WWAN_RECONNECT_ATTEMPT':     '1.3.6.1.4.1.44641.1.2.0.1',
    # igosWwanFailoverEvent       (.2)
    'WWAN_SIM_FAILOVER':          '1.3.6.1.4.1.44641.1.2.0.2',
    'WWAN_SIM_SWITCH':            '1.3.6.1.4.1.44641.1.2.0.2',
    # igosWwanBearerUp/Down       (.4 / .5)
    'WWAN_BEARER_UP':             '1.3.6.1.4.1.44641.1.2.0.4',
    'WWAN_BEARER_DOWN':           '1.3.6.1.4.1.44641.1.2.0.5',
    # igosWwanDataLimitWarning/Reached (.7 / .8)
    'WWAN_USAGE_WARNING':         '1.3.6.1.4.1.44641.1.2.0.7',
    'WWAN_USAGE_LIMIT_EXCEEDED':  '1.3.6.1.4.1.44641.1.2.0.8',
}


class AlertAdapterBase(ABC):
    """Base class for protocol-specific alert adapters."""

    @abstractmethod
    async def on_alert(self, alert: Dict[str, Any]) -> None:
        """Handle one normalized alert envelope."""


class AlertSubscriptionRunner:
    """Attach adapters to AlertBus subscriptions.

    Runner owns AlertBus subscription ids and dispatches each matching alert to
    all registered adapters.
    """

    def __init__(self, client: WWANClient) -> None:
        self.client = client
        self.adapters: list[AlertAdapterBase] = []
        self.subscription_ids: list[int] = []

    def add_adapter(self, adapter: AlertAdapterBase) -> None:
        self.adapters.append(adapter)

    async def _dispatch_alert(self, alert: Dict[str, Any]) -> None:
        for adapter in self.adapters:
            try:
                await adapter.on_alert(alert)
            except Exception as exc:
                logger.warning('Alert adapter %s failed: %s', adapter.__class__.__name__, exc)

    def start(
        self,
        *,
        interface_number: int = -1,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        code: Optional[str] = None,
    ) -> int:
        """Start AlertBus subscription and return subscription id."""
        subscription_id = self.client.subscribe_alerts(
            self._dispatch_alert,
            interface_number=interface_number,
            category=category,
            severity=severity,
            code=code,
        )
        self.subscription_ids.append(subscription_id)
        return subscription_id

    def stop_all(self) -> None:
        """Stop all runner-owned subscriptions."""
        for sub_id in self.subscription_ids:
            self.client.unsubscribe_alerts(sub_id)
        self.subscription_ids.clear()


class RestAlertAdapter(AlertAdapterBase):
    """In-memory store for REST exposure.

    A REST service can wrap this adapter and expose:
    - ``get_recent()``: bounded recent alert history
    - ``get_active()``: currently open alerts by id
    """

    def __init__(self, history_limit: int = 500) -> None:
        self.history_limit = max(1, int(history_limit))
        self.recent: Deque[Dict[str, Any]] = deque(maxlen=self.history_limit)
        self.active_by_id: Dict[str, Dict[str, Any]] = {}

    async def on_alert(self, alert: Dict[str, Any]) -> None:
        self.recent.append(alert)
        state = str(alert.get('state', 'open')).lower()
        alert_id = str(alert.get('id', ''))
        if not alert_id:
            return

        if state in ('cleared', 'acked'):
            self.active_by_id.pop(alert_id, None)
        else:
            self.active_by_id[alert_id] = alert

    def get_recent(self, limit: int = 100) -> list[Dict[str, Any]]:
        """Return the most recent alerts."""
        limit = max(1, int(limit))
        items = list(self.recent)
        return items[-limit:]

    def get_active(self) -> list[Dict[str, Any]]:
        """Return active (open) alerts."""
        return list(self.active_by_id.values())


class MqttAlertAdapter(AlertAdapterBase):
    """MQTT adapter skeleton.

        Publishes alerts to:
            igos/alerts/<category>/<source>

    Uses an injected ``publish_func(topic, payload, qos, retain)`` callback to
    avoid hard-coding a specific MQTT dependency in WWAN core.  Existing
    services can pass a thin wrapper over paho-mqtt or another client library.
    """

    def __init__(
        self,
        publish_func: Callable[[str, str, int, bool], Any],
        *,
        topic_prefix: str = 'igos/alerts',
        qos: int = 1,
        retain: bool = False,
    ) -> None:
        self.publish_func = publish_func
        self.topic_prefix = topic_prefix.rstrip('/')
        self.qos = int(qos)
        self.retain = bool(retain)

    async def on_alert(self, alert: Dict[str, Any]) -> None:
        category = str(alert.get('category', 'connectivity')).strip() or 'connectivity'
        source = str(alert.get('source', 'unknown')).strip() or 'unknown'
        topic = f'{self.topic_prefix}/{category}/{source}'
        payload = json.dumps(alert, separators=(',', ':'))
        result = self.publish_func(topic, payload, self.qos, self.retain)
        if hasattr(result, '__await__'):
            await result


class SnmpAlertAdapter(AlertAdapterBase):
    """SNMP trap adapter skeleton.

    Uses an injected ``send_trap_func(oid, varbinds)`` callback to keep SNMP
    transport and library choices outside WWAN core.
    """

    def __init__(
        self,
        send_trap_func: Callable[[str, Dict[str, Any]], Any],
        *,
        default_oid: str = '1.3.6.1.4.1.44641.1.2.0.255',
    ) -> None:
        self.send_trap_func = send_trap_func
        self.default_oid = default_oid

    async def on_alert(self, alert: Dict[str, Any]) -> None:
        code = str(alert.get('code', 'WWAN_EVENT'))
        oid = ALERT_CODE_TO_SNMP_OID.get(code, self.default_oid)
        varbinds = {
            'alertId': alert.get('id', ''),
            'alertCode': code,
            'alertSeverity': alert.get('severity', 'info'),
            'alertCategory': alert.get('category', 'modem'),
            'alertSource': alert.get('source', ''),
            'alertMessage': alert.get('message', ''),
            'alertState': alert.get('state', 'open'),
            'alertTimestamp': alert.get('timestamp', ''),
            'alertInterface': alert.get('interface_number', -1),
        }
        result = self.send_trap_func(oid, varbinds)
        if hasattr(result, '__await__'):
            await result
