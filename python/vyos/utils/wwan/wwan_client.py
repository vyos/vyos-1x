#!/usr/bin/env python3
# Copyright (C) 2024-2026 IGOS and contributors
# SPDX-License-Identifier: GPL-2.0-or-later
#
# wwan_client.py — WWAN D-Bus Client Library
#
# Import this module to interact with the IGOS WWAN modem management service.
# All D-Bus complexity is hidden behind simple async method calls.
#
# Quick start:
#
#     from wwan_client import WWANClient
#
#     async def main():
#         async with WWANClient() as client:
#             # Connect bearer
#             await client.connect_bearer(0)
#
#             # Poll status
#             status = await client.get_bearer_status(0)
#             print(status)  # "connected" or "disconnected"
#
#             # Full status dict
#             info = await client.get_status(0)
#             print(info['state'], info['signal_quality'])

"""
WWAN D-Bus Client Library
==========================

Provides a high-level Python interface to the IGOS WWAN modem management
service (com.igos.IgosModemManager).

Classes
-------
WWANClient
    Async context-manager client wrapping all 9 D-Bus methods across
    the Control and Interface endpoints.

WWANClientSync
    Synchronous wrapper around WWANClient for callers that don't use
    asyncio.  Each method runs the event loop internally.

Exceptions
----------
WWANError            Base exception for all client errors.
WWANConnectionError  Raised on D-Bus connection / introspection failures.
WWANConfigError      Raised when SetConfiguration is rejected.
WWANTimeoutError     Raised when a D-Bus call exceeds the deadline.

Constants
---------
BUS_NAME             "com.igos.IgosModemManager"
CONTROL_PATH         "/com/igos/IgosModemManager/Control"
CONTROL_IFACE        "com.igos.IgosModemManager.Control"
INTERFACE_IFACE      "com.igos.IgosModemManager.Interface"
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional

from dbus_next import Variant  # pylint: disable=import-error
from dbus_next.aio import MessageBus  # pylint: disable=import-error
from dbus_next.constants import BusType  # pylint: disable=import-error
from dbus_next.errors import DBusError  # pylint: disable=import-error

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────

BUS_NAME = "com.igos.IgosModemManager"
CONTROL_PATH = "/com/igos/IgosModemManager/Control"
CONTROL_IFACE = "com.igos.IgosModemManager.Control"
ALERT_PATH = "/com/igos/IgosModemManager/AlertBus"
ALERT_IFACE = "com.igos.IgosModemManager.AlertBus"
INTERFACE_IFACE = "com.igos.IgosModemManager.Interface"

# ─── Exceptions ─────────────────────────────────────────────────────────────

class WWANError(Exception):
    """Base exception for WWAN client errors."""

class WWANConnectionError(WWANError):
    """Could not connect to the D-Bus service or introspect an object."""

class WWANConfigError(WWANError):
    """SetConfiguration was rejected (validation or application failure)."""

class WWANTimeoutError(WWANError):
    """A D-Bus method call timed out."""

# ─── D-Bus variant helpers ──────────────────────────────────────────────────

def _python_to_variant(value: Any) -> Variant:
    """Recursively convert a Python value to a ``dbus_next.Variant``.

    Handles dicts (``a{sv}``), lists (typed arrays), bools, ints, floats,
    and strings.  Unknown types fall back to string conversion.
    """
    if isinstance(value, dict):
        return Variant('a{sv}', {k: _python_to_variant(v)
                                  for k, v in value.items()})
    if isinstance(value, list):
        if not value:
            return Variant('as', [])
        if all(isinstance(x, str) for x in value):
            return Variant('as', value)
        if all(isinstance(x, int) and not isinstance(x, bool) for x in value):
            return Variant('ai', value)
        if all(isinstance(x, (int, float)) and not isinstance(x, bool)
               for x in value):
            return Variant('ad', [float(x) for x in value])
        return Variant('av', [_python_to_variant(x) for x in value])
    if isinstance(value, bool):
        return Variant('b', value)
    if isinstance(value, int):
        if -2_147_483_648 <= value <= 2_147_483_647:
            return Variant('i', value)
        return Variant('x', value)
    if isinstance(value, float):
        return Variant('d', value)
    if isinstance(value, str):
        return Variant('s', value)
    return Variant('s', str(value))


def _variant_to_python(value: Any) -> Any:
    """Recursively unwrap ``dbus_next.Variant`` objects to plain Python types.

    Handles nested dicts and lists of variants.
    """
    if isinstance(value, Variant):
        return _variant_to_python(value.value)
    if isinstance(value, dict):
        return {k: _variant_to_python(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_variant_to_python(v) for v in value]
    return value


def _interface_path(interface_number: int) -> str:
    """Return the D-Bus object path for an interface index."""
    return f"/com/igos/IgosModemManager/Interface{interface_number}"


# ─── Async Client ───────────────────────────────────────────────────────────

class WWANClient:
    """Async D-Bus client for the IGOS WWAN modem management service.

    Use as an async context manager to ensure the bus is connected and
    properly closed::

        async with WWANClient() as client:
            await client.connect_bearer(0)
            status = await client.get_bearer_status(0)

    Or manage the lifecycle manually::

        client = WWANClient()
        await client.open()
        ...
        await client.close()

    Parameters
    ----------
    bus_type : BusType, optional
        ``BusType.SYSTEM`` (default) or ``BusType.SESSION``.
    """

    def __init__(self, bus_type: BusType = BusType.SYSTEM) -> None:
        self._bus_type = bus_type
        self._bus: Optional[MessageBus] = None
        self._ctrl_iface = None
        self._alert_iface = None
        # Cache of introspected per-interface proxies: {int: iface_proxy}
        self._iface_cache: Dict[int, Any] = {}
        self._alert_subscriptions: Dict[int, Dict[str, Any]] = {}
        self._next_alert_subscription_id = 1

    # ── lifecycle ────────────────────────────────────────────────────────

    async def open(self) -> "WWANClient":
        """Connect to the D-Bus system bus and introspect the Control object."""
        try:
            self._bus = await MessageBus(bus_type=self._bus_type).connect()
            intro = await self._bus.introspect(BUS_NAME, CONTROL_PATH)
            obj = self._bus.get_proxy_object(BUS_NAME, CONTROL_PATH, intro)
            self._ctrl_iface = obj.get_interface(CONTROL_IFACE)

            # Alert bus is optional for backward compatibility with older daemons.
            try:
                alert_intro = await self._bus.introspect(BUS_NAME, ALERT_PATH)
                alert_obj = self._bus.get_proxy_object(BUS_NAME, ALERT_PATH, alert_intro)
                self._alert_iface = alert_obj.get_interface(ALERT_IFACE)
            except Exception:
                self._alert_iface = None
        except Exception as exc:
            raise WWANConnectionError(
                f"Failed to connect to {BUS_NAME}: {exc}"
            ) from exc
        return self

    async def close(self) -> None:
        """Disconnect from the D-Bus bus."""
        self.clear_alert_subscriptions()
        self._iface_cache.clear()
        if self._bus:
            self._bus.disconnect()
            self._bus = None

    async def __aenter__(self) -> "WWANClient":
        return await self.open()

    async def __aexit__(self, *exc_info) -> None:
        await self.close()

    # ── internal helpers ─────────────────────────────────────────────────

    async def _get_iface(self, interface_number: int):
        """Introspect and cache the proxy for ``Interface{N}``."""
        if interface_number in self._iface_cache:
            return self._iface_cache[interface_number]
        path = _interface_path(interface_number)
        try:
            intro = await self._bus.introspect(BUS_NAME, path)
            obj = self._bus.get_proxy_object(BUS_NAME, path, intro)
            iface = obj.get_interface(INTERFACE_IFACE)
            self._iface_cache[interface_number] = iface
            return iface
        except Exception as exc:
            raise WWANConnectionError(
                f"Cannot introspect {path}: {exc}"
            ) from exc

    def _invalidate_cache(self, interface_number: int) -> None:
        """Remove a cached proxy (e.g. after RemoveInterface)."""
        self._iface_cache.pop(interface_number, None)

    # ── Control interface ────────────────────────────────────────────────

    async def add_interface(self, interface_number: int) -> str:
        """Create a modem interface on the service.

        Idempotent — returns success even if the interface already exists.

        Parameters
        ----------
        interface_number : int
            Interface index (0, 1, …).

        Returns
        -------
        str
            Service response, e.g. ``"Interface 0 ready"``.
        """
        try:
            return await self._ctrl_iface.call_add_interface(interface_number)
        except DBusError as exc:
            err = str(exc).lower()
            if "already exists" in err or "already exported" in err:
                return f"Interface {interface_number} already exists"
            raise WWANError(f"AddInterface failed: {exc}") from exc

    async def remove_interface(self, interface_number: int) -> str:
        """Remove a modem interface from the service.

        Parameters
        ----------
        interface_number : int
            Interface index to remove.

        Returns
        -------
        str
            Service response, e.g. ``"Interface 0 removed"``.
        """
        try:
            result = await self._ctrl_iface.call_remove_interface(
                interface_number
            )
            self._invalidate_cache(interface_number)
            return result
        except DBusError as exc:
            raise WWANError(f"RemoveInterface failed: {exc}") from exc

    # ── Interface methods ────────────────────────────────────────────────

    async def set_configuration(
        self,
        interface_number: int,
        config: Dict[str, Any],
    ) -> str:
        """Apply a configuration dictionary to a modem interface.

        The configuration is merged with the service's current config and
        validated before being applied to the FSM.

        Parameters
        ----------
        interface_number : int
            Interface index (0, 1, …).
        config : dict
            Configuration dictionary.  Accepted keys include:

            **Top-level scalars:**
            ``connection_mode``, ``primary_sim_slot``, ``sim_failover``,
            ``android_apn_discovery``, ``network_mode``,
            ``mtu`` (interface MTU ceiling / fallback; default 1420),
            ``network_scan_timeout``, ``connection_timeout``,
            ``registration_timeout``, ``normal_monitoring_interval``,
            ``verbose_logging``, ``log_level``, ``hardware_reset_enabled``,
            ``max_hardware_resets``, ``hardware_reset_cooldown``,
            ``data_usage_monitoring_interval``,
            ``sim_failover_connect_retries``, ``sim_failover_revert_timer``,
            ``sim_failover_signal_loss_timer``, ``sim_failover_signal_threshold``,
            ``sim_failback_enabled``, ``sim_failback_check_interval``.

            **Nested dicts:**
            ``enhanced_reconnection`` — keys: ``enabled``,
            ``signal_threshold``, ``retry_interval_good_signal``,
            ``retry_interval_poor_signal``, ``max_wait_for_signal``,
            ``signal_check_interval``, ``signal_strength_buffer``.

            ``connectivity_monitoring`` — keys: ``enabled``, ``interval``,
            ``timeout``, ``retry_count``, ``failure_threshold``,
            ``test_ipv4``, ``test_ipv6``, ``require_both``,
            ``ipv4_targets``, ``ipv6_targets``.

            ``interface_management`` — keys: ``enabled``,
            ``bearer_disconnect_delay``, ``registration_recovery_delay``,
            ``registration_flap_count`` (0 = disabled; if this many
            debounced registration losses occur within
            ``registration_flap_window`` seconds, SIM failover is
            triggered), ``registration_flap_window``,
            ``ip_change_delay``, ``ensure_link_up_on_connect``,
            ``monitor_bearer_state``, ``monitor_ip_changes``,
            ``interface_up_timeout``.

            ``failed_retry`` — keys: ``enabled`` (bool, default True),
            ``intervals`` (list of ints in seconds, default
            ``[600, 1800, 3600, 7200]`` — stepped backoff from FAILED
            state, carrier-friendly), ``max_interval`` (int, cap once list exhausted,
            default 7200), ``escalation_threshold`` (int, default 3 —
            after this many consecutive failed retries, escalate to a
            modem disable/enable cycle to force EPS detach/reattach;
            0 disables escalation).

            ``sim_slots`` — list of per-SIM dicts, each with:
            ``slot``, ``enabled`` (bool, default True — both slots enabled;
            VyOS ``disable`` command maps to False), ``apn`` (str or ``{name, username,
            password, auth_type}``), ``pdp_type``, ``roaming``, ``pin``,
            ``puk``, ``iccid`` (ICCID lock — 19-20 digit string; if set,
            only the SIM with this ICCID is accepted in the slot — empty
            string means no lock), ``supported_bands`` (``all`` or specific
            band names — use ``network-mode`` for technology-level control),
            ``preferred_carrier`` (MCCMNC code or friendly name —
            per-SIM only, each SIM has its own carrier),
            ``enable_network_scan`` (diagnostic scan — results appear
            in status ``available_networks``; per-SIM only),
            ``data_limit_size``, ``data_limit_action``,
            ``data_limit_billing_date``,
            ``data_limit_warning`` (comma-separated pct thresholds,
            e.g. ``[75, 90, 95]``; empty list = no warnings),
            ``mtu`` (per-SIM MTU override; 0 = use interface ``mtu``).

        Returns
        -------
        str
            Success message, e.g.
            ``"Configuration applied to interface 0"``.

        Raises
        ------
        WWANConfigError
            If validation fails or the FSM rejects the config.
        """
        iface = await self._get_iface(interface_number)
        dbus_config = {k: _python_to_variant(v) for k, v in config.items()}
        try:
            return await iface.call_set_configuration(dbus_config)
        except DBusError as exc:
            raise WWANConfigError(
                f"SetConfiguration rejected: {exc}"
            ) from exc

    async def connect(self, interface_number: int) -> str:
        """Request a data connection (legacy method).

        In ``always-on`` mode returns a descriptive message.  In
        ``connect-on-demand`` and ``dial-on-demand`` modes returns
        ``"accepted"`` (fire-and-forget).

        Parameters
        ----------
        interface_number : int
            Interface index.

        Returns
        -------
        str
            Service response.
        """
        iface = await self._get_iface(interface_number)
        try:
            return await iface.call_connect()
        except DBusError as exc:
            raise WWANError(f"Connect failed: {exc}") from exc

    async def disconnect(self, interface_number: int) -> str:
        """Request disconnection (legacy method).

        In ``always-on`` mode performs a full disconnect.  In on-demand
        modes fires ``ENTER_IDLE`` (bearer drops, modem stays registered).

        Parameters
        ----------
        interface_number : int
            Interface index.

        Returns
        -------
        str
            Service response.
        """
        iface = await self._get_iface(interface_number)
        try:
            return await iface.call_disconnect()
        except DBusError as exc:
            raise WWANError(f"Disconnect failed: {exc}") from exc

    async def connect_bearer(self, interface_number: int) -> str:
        """Request bearer establishment (fire-and-forget).

        Always returns ``"accepted"``.  Poll :meth:`get_bearer_status` to
        observe the actual outcome.

        Parameters
        ----------
        interface_number : int
            Interface index.

        Returns
        -------
        str
            ``"accepted"``
        """
        iface = await self._get_iface(interface_number)
        try:
            return await iface.call_connect_bearer()
        except DBusError as exc:
            raise WWANError(f"ConnectBearer failed: {exc}") from exc

    async def disconnect_bearer(self, interface_number: int) -> str:
        """Request bearer teardown (fire-and-forget).

        Drops the data bearer but keeps the modem registered on the
        network.  SMS remains available.  Always returns ``"accepted"``.
        Poll :meth:`get_bearer_status` to observe the actual outcome.

        Parameters
        ----------
        interface_number : int
            Interface index.

        Returns
        -------
        str
            ``"accepted"``
        """
        iface = await self._get_iface(interface_number)
        try:
            return await iface.call_disconnect_bearer()
        except DBusError as exc:
            raise WWANError(f"DisconnectBearer failed: {exc}") from exc

    async def get_bearer_status(self, interface_number: int) -> str:
        """Poll the current bearer state.

        Parameters
        ----------
        interface_number : int
            Interface index.

        Returns
        -------
        str
            ``"connected"`` when Bearer is active (FSM in CONNECTED),
            ``"disconnected"`` otherwise.
        """
        iface = await self._get_iface(interface_number)
        try:
            return await iface.call_get_bearer_status()
        except DBusError as exc:
            raise WWANError(f"GetBearerStatus failed: {exc}") from exc

    async def get_status(self, interface_number: int) -> Dict[str, Any]:
        """Retrieve comprehensive modem / interface status.

        Returns a plain Python dict (all ``dbus_next.Variant`` wrappers
        are recursively unwrapped).

        Parameters
        ----------
        interface_number : int
            Interface index.

        Returns
        -------
        dict
            Keys include (among many others): ``fsm_state``,
            ``modem_model``, ``modem_imei``, ``modem_phone_number``,
            ``modem_phone_numbers``, ``modem_hardware_revision``,
            ``modem_power_state``, ``modem_power_state_name``,
            ``signal_percent``,
            ``signal_dbm``, ``signal_rssi``, ``signal_rsrp``,
            ``signal_rsrq``, ``signal_snr``, ``signal_technology``,
            ``access_technology_name``, ``current_bands``,
            ``modem_state_failed_reason``,
            ``modem_state_failed_reason_name``,
            ``operator_name``, ``operator_code``,
            ``registration_state``, ``connection_mode``,
            ``active_sim_slot``, ``configured_sim_slot``,
            ``is_on_failover_sim``, ``sim_imsi``, ``sim_iccid``,
            ``ipv4_address``, ``ipv6_address``, ``ipv4_gateway``,
            ``session_rx_bytes``, ``session_tx_bytes``,
            ``cumulative_bytes``, ``data_usage_percent``,
            ``connected_apn``, ``network_mode``.

            **Connection failure information** (populated when FSM is
            in ``FAILED`` state) —
            ``failure_reason``: human-readable description of why
            the connection failed,
            ``failure_time``: ISO-8601 timestamp of the failure,
            ``failed_apn``: the APN that was in use when the failure
            occurred,
            ``configured_apn_rejected``: ``True`` when the user's
            explicitly configured APN was rejected by the network.

            **Failback suppression** —
            ``failback_suppressed_by_connection_failure``: ``True``
            when the primary SIM's APN cascade failed and automatic
            failback is suppressed until a new configuration event.

            **Per-slot SIM identity** — for each physical SIM slot
            ``N`` (1-based): ``sim_slot_N_present``,
            ``sim_slot_N_imsi``, ``sim_slot_N_iccid``,
            ``sim_slot_N_operator``, ``sim_slot_N_mcc_mnc``,
            ``sim_slot_N_data_limit_warning`` (list of pct thresholds).
            The active slot uses live D-Bus data; inactive slots
            are probed via D-Bus with a cache fallback.

            **Active SIM data config** —
            ``active_data_limit_size`` (bytes),
            ``active_data_limit_action`` (none/disable/sim-failover/
            sim-failover-sticky),
            ``active_data_limit_billing_date`` (1-28),
            ``active_data_limit_warning`` (list of pct thresholds;
            empty = disabled).
            Shows the effective data-limit config for the currently
            active SIM (per-SIM → global fallback → defaults).

            **SIM PIN/PUK unlock status** —
            ``pin_unlock_attempted``, ``pin_unlock_failed``,
            ``puk_unlock_attempted``, ``puk_unlock_failed``,
            ``sim_permanently_locked``,
            ``pin_retries_remaining``, ``puk_retries_remaining``.

            **Network scan results** (present when a scan has been
            performed, either automatically for a friendly-name
            ``preferred_carrier`` or via ``enable_network_scan``) —
            ``available_networks``: list of dicts, each with
            ``operator_name``, ``operator_short``, ``operator_code``
            (MCCMNC), ``status`` (available/current/forbidden),
            ``access_technology`` (e.g. LTE, 5GNR).
        """
        iface = await self._get_iface(interface_number)
        try:
            raw = await iface.call_get_status()
            return _variant_to_python(raw)
        except DBusError as exc:
            raise WWANError(f"GetStatus failed: {exc}") from exc

    async def get_recent_alerts(
        self,
        limit: int = 50,
        interface_number: int = -1,
    ) -> list:
        """Fetch recent normalized alerts from the generalized AlertBus.

        Parameters
        ----------
        limit : int
            Maximum number of alerts to return.
        interface_number : int
            Interface filter; ``-1`` means all interfaces.
        """
        if not self._alert_iface:
            return []
        try:
            raw = await self._alert_iface.call_get_recent_alerts(limit, interface_number)
            return _variant_to_python(raw)
        except DBusError as exc:
            raise WWANError(f"GetRecentAlerts failed: {exc}") from exc

    async def clear_alerts(self, interface_number: int = -1) -> str:
        """Clear alert history globally (-1) or for one interface."""
        if not self._alert_iface:
            return "AlertBus unavailable"
        try:
            return await self._alert_iface.call_clear_alerts(interface_number)
        except DBusError as exc:
            raise WWANError(f"ClearAlerts failed: {exc}") from exc

    async def ack_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert by id.

        Returns ``True`` when the alert id exists, else ``False``.
        """
        if not self._alert_iface:
            return False
        try:
            return bool(await self._alert_iface.call_ack_alert(str(alert_id)))
        except DBusError as exc:
            raise WWANError(f"AckAlert failed: {exc}") from exc

    @staticmethod
    def _alert_matches(
        alert: Dict[str, Any],
        *,
        alert_type: Optional[str] = None,
        category: Optional[str] = None,
        code: Optional[str] = None,
        source: Optional[str] = None,
        state: Optional[str] = None,
        severity: Optional[str] = None,
        contains: Optional[str] = None,
        min_sequence: int = 0,
    ) -> bool:
        """Return True if an alert matches the provided filter criteria."""
        try:
            seq = int(alert.get('sequence', 0))
        except (TypeError, ValueError):
            seq = 0
        if seq <= min_sequence:
            return False

        if alert_type and str(alert.get('type', '')) != alert_type:
            return False

        if category and str(alert.get('category', '')).lower() != category.lower():
            return False

        if code and str(alert.get('code', '')) != code:
            return False

        if source and str(alert.get('source', '')) != source:
            return False

        if state and str(alert.get('state', '')).lower() != state.lower():
            return False

        if severity and str(alert.get('severity', '')).lower() != severity.lower():
            return False

        if contains:
            msg = str(alert.get('message', ''))
            if contains.lower() not in msg.lower():
                return False

        return True

    async def get_alerts_filtered(
        self,
        *,
        limit: int = 200,
        interface_number: int = -1,
        alert_type: Optional[str] = None,
        category: Optional[str] = None,
        code: Optional[str] = None,
        source: Optional[str] = None,
        state: Optional[str] = None,
        severity: Optional[str] = None,
        contains: Optional[str] = None,
        min_sequence: int = 0,
    ) -> list:
        """Fetch recent alerts and return only entries matching filters.

        Parameters
        ----------
        limit : int
            Number of recent alerts fetched from AlertBus before local filtering.
        interface_number : int
            Interface filter (`-1` means all interfaces).
        alert_type : str, optional
            Exact alert type filter.
        category : str, optional
            Alert category filter (e.g. connectivity/sim/usage).
        code : str, optional
            Exact stable machine code filter.
        source : str, optional
            Exact source filter.
        state : str, optional
            Alert state filter (`open`, `cleared`, `acked`).
        severity : str, optional
            Severity filter (`info`, `warning`, `error`, ...).
        contains : str, optional
            Case-insensitive substring match against alert message text.
        min_sequence : int
            Only return alerts with `sequence > min_sequence`.
        """
        alerts = await self.get_recent_alerts(limit=limit, interface_number=interface_number)
        return [
            a for a in alerts
            if isinstance(a, dict) and self._alert_matches(
                a,
                alert_type=alert_type,
                category=category,
                code=code,
                source=source,
                state=state,
                severity=severity,
                contains=contains,
                min_sequence=min_sequence,
            )
        ]

    def subscribe_alerts(
        self,
        callback: Callable[[Dict[str, Any]], Any],
        *,
        interface_number: int = -1,
        alert_type: Optional[str] = None,
        category: Optional[str] = None,
        code: Optional[str] = None,
        severity: Optional[str] = None,
        contains: Optional[str] = None,
        source: Optional[str] = None,
        state: Optional[str] = None,
        use_json_signal: bool = False,
    ) -> int:
        """Subscribe to AlertBus signal events with optional filtering.

        Returns a subscription id that can be passed to
        :meth:`unsubscribe_alerts`.
        """
        if not self._alert_iface:
            raise WWANConnectionError("AlertBus unavailable")

        subscription_id = self._next_alert_subscription_id
        self._next_alert_subscription_id += 1

        signal_name = 'alert_raised' if use_json_signal else 'alert'
        on_method = getattr(self._alert_iface, f'on_{signal_name}', None)
        if not on_method:
            raise WWANConnectionError(f"Signal registration method on_{signal_name} is unavailable")

        def _dispatch(alert_payload):
            try:
                if use_json_signal:
                    if isinstance(alert_payload, (str, bytes)):
                        alert = json.loads(alert_payload)
                    else:
                        alert = json.loads(str(alert_payload))
                else:
                    alert = _variant_to_python(alert_payload)

                if not isinstance(alert, dict):
                    return

                if interface_number >= 0 and int(alert.get('interface_number', -1)) != interface_number:
                    return

                if not self._alert_matches(
                    alert,
                    alert_type=alert_type,
                    category=category,
                    code=code,
                    source=source,
                    state=state,
                    severity=severity,
                    contains=contains,
                ):
                    return

                result = callback(alert)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception as exc:
                logger.debug("Alert subscription callback error: %s", exc)

        on_method(_dispatch)
        self._alert_subscriptions[subscription_id] = {
            'signal_name': signal_name,
            'callback': _dispatch,
        }
        return subscription_id

    def unsubscribe_alerts(self, subscription_id: int) -> bool:
        """Unsubscribe a previously registered alert callback."""
        sub = self._alert_subscriptions.pop(subscription_id, None)
        if not sub or not self._alert_iface:
            return False

        off_method = getattr(self._alert_iface, f"off_{sub['signal_name']}", None)
        if off_method:
            try:
                off_method(sub['callback'])
            except Exception as exc:
                logger.debug("Alert unsubscribe failed for %s: %s", subscription_id, exc)
        return True

    def clear_alert_subscriptions(self) -> None:
        """Unsubscribe all active alert callbacks for this client."""
        for subscription_id in list(self._alert_subscriptions.keys()):
            self.unsubscribe_alerts(subscription_id)

    async def monitor_alerts(
        self,
        *,
        timeout: float = 30.0,
        interface_number: int = -1,
        alert_type: Optional[str] = None,
        category: Optional[str] = None,
        code: Optional[str] = None,
        severity: Optional[str] = None,
        contains: Optional[str] = None,
        source: Optional[str] = None,
        state: Optional[str] = None,
        include_existing: bool = False,
        existing_limit: int = 50,
        use_json_signal: bool = False,
    ) -> list:
        """Collect matching alerts emitted during a monitoring window.

        This helper uses signal subscriptions under the hood and returns all
        matching alerts observed before timeout.
        """
        collected = []
        if include_existing:
            collected.extend(await self.get_alerts_filtered(
                limit=existing_limit,
                interface_number=interface_number,
                alert_type=alert_type,
                category=category,
                code=code,
                source=source,
                state=state,
                severity=severity,
                contains=contains,
            ))

        subscription_id = self.subscribe_alerts(
            lambda alert: collected.append(alert),
            interface_number=interface_number,
            alert_type=alert_type,
            category=category,
            code=code,
            severity=severity,
            contains=contains,
            source=source,
            state=state,
            use_json_signal=use_json_signal,
        )
        try:
            await asyncio.sleep(max(0.0, float(timeout)))
            return collected
        finally:
            self.unsubscribe_alerts(subscription_id)

    async def wait_for_alert(
        self,
        *,
        alert_type: Optional[str] = None,
        severity: Optional[str] = None,
        interface_number: int = -1,
        contains: Optional[str] = None,
        timeout: float = 60.0,
        poll_interval: float = 1.0,
        include_existing: bool = False,
        limit: int = 200,
    ) -> Optional[Dict[str, Any]]:
        """Wait until an alert matching criteria appears.

        Returns the first matching alert, or ``None`` if timeout expires.
        By default only *new* alerts are considered.
        """
        min_sequence = 0
        if not include_existing:
            baseline = await self.get_recent_alerts(limit=limit, interface_number=interface_number)
            for entry in baseline:
                if isinstance(entry, dict):
                    try:
                        min_sequence = max(min_sequence, int(entry.get('sequence', 0)))
                    except (TypeError, ValueError):
                        continue

        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            matches = await self.get_alerts_filtered(
                limit=limit,
                interface_number=interface_number,
                alert_type=alert_type,
                severity=severity,
                contains=contains,
                min_sequence=min_sequence,
            )
            if matches:
                return matches[0]
            await asyncio.sleep(poll_interval)

        return None

    async def get_failover_alerts(
        self,
        *,
        limit: int = 200,
        interface_number: int = -1,
        min_sequence: int = 0,
    ) -> list:
        """Convenience helper: return SIM failover/switch related alerts."""
        alerts = await self.get_recent_alerts(limit=limit, interface_number=interface_number)
        result = []
        for alert in alerts:
            if not isinstance(alert, dict):
                continue
            try:
                if int(alert.get('sequence', 0)) <= min_sequence:
                    continue
            except (TypeError, ValueError):
                continue

            alert_kind = str(alert.get('type', ''))
            msg = str(alert.get('message', '')).lower()
            if alert_kind in ('sim_failover', 'sim_switch') or 'failover' in msg:
                result.append(alert)
        return result

    async def wait_for_failover_alert(
        self,
        *,
        interface_number: int = -1,
        timeout: float = 120.0,
        poll_interval: float = 1.0,
        include_existing: bool = False,
        limit: int = 200,
    ) -> Optional[Dict[str, Any]]:
        """Convenience helper: wait for a SIM failover-related alert."""
        min_sequence = 0
        if not include_existing:
            baseline = await self.get_recent_alerts(limit=limit, interface_number=interface_number)
            for entry in baseline:
                if isinstance(entry, dict):
                    try:
                        min_sequence = max(min_sequence, int(entry.get('sequence', 0)))
                    except (TypeError, ValueError):
                        continue

        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            matches = await self.get_failover_alerts(
                limit=limit,
                interface_number=interface_number,
                min_sequence=min_sequence,
            )
            if matches:
                return matches[0]
            await asyncio.sleep(poll_interval)

        return None

    # ── SMS methods ──────────────────────────────────────────────────────

    async def send_sms(
        self, interface_number: int, recipient: str, message: str
    ) -> Dict[str, Any]:
        """Send an SMS message via the modem.

        Parameters
        ----------
        interface_number : int
            Interface index.
        recipient : str
            Destination phone number.
        message : str
            SMS text body (up to 160 chars for single SMS, longer texts
            are concatenated automatically by ModemManager).

        Returns
        -------
        dict
            ``{'status': 'sent', 'message_id': N}``
        """
        iface = await self._get_iface(interface_number)
        try:
            raw = await iface.call_send_sms(recipient, message)
            return _variant_to_python(raw)
        except DBusError as exc:
            raise WWANError(f"SendSms failed: {exc}") from exc

    async def list_sms(self, interface_number: int) -> list:
        """List all stored SMS messages for the current SIM.

        Returns
        -------
        list[dict]
            Each dict has keys: ``id``, ``direction``, ``number``,
            ``text``, ``timestamp``, ``status``, ``read``.
        """
        iface = await self._get_iface(interface_number)
        try:
            raw = await iface.call_list_sms()
            return _variant_to_python(raw)
        except DBusError as exc:
            raise WWANError(f"ListSms failed: {exc}") from exc

    async def read_sms(
        self, interface_number: int, message_id: int
    ) -> Dict[str, Any]:
        """Read a specific SMS message by ID.

        Marks incoming messages as read on first access.

        Parameters
        ----------
        interface_number : int
            Interface index.
        message_id : int
            Message ID from :meth:`list_sms`.

        Returns
        -------
        dict
            Full message record.
        """
        iface = await self._get_iface(interface_number)
        try:
            raw = await iface.call_read_sms(message_id)
            return _variant_to_python(raw)
        except DBusError as exc:
            raise WWANError(f"ReadSms failed: {exc}") from exc

    async def delete_sms(
        self, interface_number: int, message_id: int
    ) -> Dict[str, Any]:
        """Delete a specific SMS message by ID.

        Parameters
        ----------
        interface_number : int
            Interface index.
        message_id : int
            Message ID to delete.

        Returns
        -------
        dict
            ``{'status': 'deleted', 'message_id': N}``
        """
        iface = await self._get_iface(interface_number)
        try:
            raw = await iface.call_delete_sms(message_id)
            return _variant_to_python(raw)
        except DBusError as exc:
            raise WWANError(f"DeleteSms failed: {exc}") from exc

    async def delete_all_sms(self, interface_number: int) -> Dict[str, Any]:
        """Delete all stored SMS messages for the current SIM.

        Returns
        -------
        dict
            ``{'status': 'deleted', 'count': 0}``
        """
        iface = await self._get_iface(interface_number)
        try:
            raw = await iface.call_delete_all_sms()
            return _variant_to_python(raw)
        except DBusError as exc:
            raise WWANError(f"DeleteAllSms failed: {exc}") from exc

    # ── convenience helpers ──────────────────────────────────────────────

    async def wait_for_bearer(
        self,
        interface_number: int,
        target: str = "connected",
        timeout: float = 60.0,
        poll_interval: float = 1.0,
    ) -> bool:
        """Poll :meth:`get_bearer_status` until it matches *target*.

        Parameters
        ----------
        interface_number : int
            Interface index.
        target : str
            Desired status — ``"connected"`` or ``"disconnected"``.
        timeout : float
            Maximum seconds to wait before returning ``False``.
        poll_interval : float
            Seconds between status polls.

        Returns
        -------
        bool
            ``True`` if the target state was reached, ``False`` on timeout.
        """
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            status = await self.get_bearer_status(interface_number)
            if status == target:
                return True
            await asyncio.sleep(poll_interval)
        return False

    async def is_connected(self, interface_number: int) -> bool:
        """Shorthand: check if the bearer is currently up.

        Returns
        -------
        bool
        """
        return (await self.get_bearer_status(interface_number)) == "connected"

    async def connect_bearer_and_wait(
        self,
        interface_number: int,
        timeout: float = 60.0,
        poll_interval: float = 1.0,
    ) -> bool:
        """Request bearer connect and block until it comes up (or timeout).

        Convenience wrapper that calls :meth:`connect_bearer` (fire-and-
        forget) and then polls :meth:`get_bearer_status` until the bearer
        reaches ``"connected"``.

        Parameters
        ----------
        interface_number : int
            Interface index.
        timeout : float
            Maximum seconds to wait for the bearer to come up.
        poll_interval : float
            Seconds between status polls.

        Returns
        -------
        bool
            ``True`` if the bearer reached ``"connected"`` before timeout,
            ``False`` otherwise.  Raises :class:`WWANError` if the service
            rejects the connect request (e.g. interface is in airplane
            mode — ``com.igos.IgosModemManager.AdminDisabled``).
        """
        await self.connect_bearer(interface_number)
        return await self.wait_for_bearer(
            interface_number, target="connected",
            timeout=timeout, poll_interval=poll_interval)

    async def disconnect_bearer_and_wait(
        self,
        interface_number: int,
        timeout: float = 30.0,
        poll_interval: float = 1.0,
    ) -> bool:
        """Request bearer disconnect and block until it drops (or timeout).

        Companion to :meth:`connect_bearer_and_wait`.  Calls
        :meth:`disconnect_bearer` (fire-and-forget) and then polls
        :meth:`get_bearer_status` until the bearer reaches
        ``"disconnected"``.

        Returns
        -------
        bool
            ``True`` if the bearer reached ``"disconnected"`` before
            timeout, ``False`` otherwise.
        """
        await self.disconnect_bearer(interface_number)
        return await self.wait_for_bearer(
            interface_number, target="disconnected",
            timeout=timeout, poll_interval=poll_interval)


# ─── Synchronous wrapper ────────────────────────────────────────────────────

class WWANClientSync:
    """Synchronous (blocking) wrapper around :class:`WWANClient`.

    Intended for scripts, CLI tools, and environments where ``async/await``
    is not available.  Each call spins up a short-lived event loop.

    Example::

        from wwan_client import WWANClientSync

        client = WWANClientSync()
        client.connect_bearer(0)
        print(client.get_bearer_status(0))   # "connected"
        info = client.get_status(0)
        print(info['state'])
    """

    def __init__(self, bus_type: BusType = BusType.SYSTEM) -> None:
        self._bus_type = bus_type

    def _run(self, coro):
        """Run an async coroutine synchronously."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already inside an event loop — use a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return asyncio.run(coro)

    async def _call(self, method_name: str, interface_number: int, **kwargs):
        async with WWANClient(bus_type=self._bus_type) as client:
            method = getattr(client, method_name)
            return await method(interface_number, **kwargs)

    # ── Control ──────────────────────────────────────────────────────────

    def add_interface(self, interface_number: int) -> str:
        """Create a modem interface.  See :meth:`WWANClient.add_interface`."""
        return self._run(self._call("add_interface", interface_number))

    def remove_interface(self, interface_number: int) -> str:
        """Remove a modem interface.  See :meth:`WWANClient.remove_interface`."""
        return self._run(self._call("remove_interface", interface_number))

    # ── Interface ────────────────────────────────────────────────────────

    def set_configuration(
        self, interface_number: int, config: Dict[str, Any]
    ) -> str:
        """Apply configuration.  See :meth:`WWANClient.set_configuration`."""
        async def _inner():
            async with WWANClient(bus_type=self._bus_type) as client:
                return await client.set_configuration(interface_number, config)
        return self._run(_inner())

    def connect(self, interface_number: int) -> str:
        """Legacy connect.  See :meth:`WWANClient.connect`."""
        return self._run(self._call("connect", interface_number))

    def disconnect(self, interface_number: int) -> str:
        """Legacy disconnect.  See :meth:`WWANClient.disconnect`."""
        return self._run(self._call("disconnect", interface_number))

    def connect_bearer(self, interface_number: int) -> str:
        """Fire-and-forget bearer connect.  See :meth:`WWANClient.connect_bearer`."""
        return self._run(self._call("connect_bearer", interface_number))

    def disconnect_bearer(self, interface_number: int) -> str:
        """Fire-and-forget bearer disconnect.  See :meth:`WWANClient.disconnect_bearer`."""
        return self._run(self._call("disconnect_bearer", interface_number))

    def connect_bearer_and_wait(
        self, interface_number: int,
        timeout: float = 60.0, poll_interval: float = 1.0,
    ) -> bool:
        """Connect bearer and block until up.  See :meth:`WWANClient.connect_bearer_and_wait`."""
        async def _inner():
            async with WWANClient(bus_type=self._bus_type) as client:
                return await client.connect_bearer_and_wait(
                    interface_number, timeout=timeout,
                    poll_interval=poll_interval)
        return self._run(_inner())

    def disconnect_bearer_and_wait(
        self, interface_number: int,
        timeout: float = 30.0, poll_interval: float = 1.0,
    ) -> bool:
        """Disconnect bearer and block until down.  See :meth:`WWANClient.disconnect_bearer_and_wait`."""
        async def _inner():
            async with WWANClient(bus_type=self._bus_type) as client:
                return await client.disconnect_bearer_and_wait(
                    interface_number, timeout=timeout,
                    poll_interval=poll_interval)
        return self._run(_inner())

    def get_bearer_status(self, interface_number: int) -> str:
        """Poll bearer state.  See :meth:`WWANClient.get_bearer_status`."""
        return self._run(self._call("get_bearer_status", interface_number))

    def get_status(self, interface_number: int) -> Dict[str, Any]:
        """Full status dict.  See :meth:`WWANClient.get_status`."""
        return self._run(self._call("get_status", interface_number))

    def get_recent_alerts(self, limit: int = 50, interface_number: int = -1) -> list:
        """Fetch recent alerts.  See :meth:`WWANClient.get_recent_alerts`."""
        async def _inner():
            async with WWANClient(bus_type=self._bus_type) as client:
                return await client.get_recent_alerts(limit=limit, interface_number=interface_number)
        return self._run(_inner())

    def clear_alerts(self, interface_number: int = -1) -> str:
        """Clear alert history.  See :meth:`WWANClient.clear_alerts`."""
        async def _inner():
            async with WWANClient(bus_type=self._bus_type) as client:
                return await client.clear_alerts(interface_number=interface_number)
        return self._run(_inner())

    def ack_alert(self, alert_id: str) -> bool:
        """Acknowledge alert by id. See :meth:`WWANClient.ack_alert`."""
        async def _inner():
            async with WWANClient(bus_type=self._bus_type) as client:
                return await client.ack_alert(alert_id=alert_id)
        return self._run(_inner())

    def get_alerts_filtered(
        self,
        *,
        limit: int = 200,
        interface_number: int = -1,
        alert_type: Optional[str] = None,
        category: Optional[str] = None,
        code: Optional[str] = None,
        source: Optional[str] = None,
        state: Optional[str] = None,
        severity: Optional[str] = None,
        contains: Optional[str] = None,
        min_sequence: int = 0,
    ) -> list:
        """Filtered alerts helper.  See :meth:`WWANClient.get_alerts_filtered`."""
        async def _inner():
            async with WWANClient(bus_type=self._bus_type) as client:
                return await client.get_alerts_filtered(
                    limit=limit,
                    interface_number=interface_number,
                    alert_type=alert_type,
                    category=category,
                    code=code,
                    source=source,
                    state=state,
                    severity=severity,
                    contains=contains,
                    min_sequence=min_sequence,
                )
        return self._run(_inner())

    def monitor_alerts(
        self,
        *,
        timeout: float = 30.0,
        interface_number: int = -1,
        alert_type: Optional[str] = None,
        category: Optional[str] = None,
        code: Optional[str] = None,
        severity: Optional[str] = None,
        contains: Optional[str] = None,
        source: Optional[str] = None,
        state: Optional[str] = None,
        include_existing: bool = False,
        existing_limit: int = 50,
        use_json_signal: bool = False,
    ) -> list:
        """Block and collect matching alerts for *timeout* seconds."""
        async def _inner():
            async with WWANClient(bus_type=self._bus_type) as client:
                return await client.monitor_alerts(
                    timeout=timeout,
                    interface_number=interface_number,
                    alert_type=alert_type,
                    category=category,
                    code=code,
                    severity=severity,
                    contains=contains,
                    source=source,
                    state=state,
                    include_existing=include_existing,
                    existing_limit=existing_limit,
                    use_json_signal=use_json_signal,
                )
        return self._run(_inner())

    def wait_for_alert(
        self,
        *,
        alert_type: Optional[str] = None,
        severity: Optional[str] = None,
        interface_number: int = -1,
        contains: Optional[str] = None,
        timeout: float = 60.0,
        poll_interval: float = 1.0,
        include_existing: bool = False,
        limit: int = 200,
    ) -> Optional[Dict[str, Any]]:
        """Blocking alert wait helper.  See :meth:`WWANClient.wait_for_alert`."""
        async def _inner():
            async with WWANClient(bus_type=self._bus_type) as client:
                return await client.wait_for_alert(
                    alert_type=alert_type,
                    severity=severity,
                    interface_number=interface_number,
                    contains=contains,
                    timeout=timeout,
                    poll_interval=poll_interval,
                    include_existing=include_existing,
                    limit=limit,
                )
        return self._run(_inner())

    def get_failover_alerts(
        self,
        *,
        limit: int = 200,
        interface_number: int = -1,
        min_sequence: int = 0,
    ) -> list:
        """Failover-alert helper.  See :meth:`WWANClient.get_failover_alerts`."""
        async def _inner():
            async with WWANClient(bus_type=self._bus_type) as client:
                return await client.get_failover_alerts(
                    limit=limit,
                    interface_number=interface_number,
                    min_sequence=min_sequence,
                )
        return self._run(_inner())

    def wait_for_failover_alert(
        self,
        *,
        interface_number: int = -1,
        timeout: float = 120.0,
        poll_interval: float = 1.0,
        include_existing: bool = False,
        limit: int = 200,
    ) -> Optional[Dict[str, Any]]:
        """Blocking failover-alert wait helper. See :meth:`WWANClient.wait_for_failover_alert`."""
        async def _inner():
            async with WWANClient(bus_type=self._bus_type) as client:
                return await client.wait_for_failover_alert(
                    interface_number=interface_number,
                    timeout=timeout,
                    poll_interval=poll_interval,
                    include_existing=include_existing,
                    limit=limit,
                )
        return self._run(_inner())

    # ── SMS ──────────────────────────────────────────────────────────────

    def send_sms(
        self, interface_number: int, recipient: str, message: str
    ) -> Dict[str, Any]:
        """Send SMS.  See :meth:`WWANClient.send_sms`."""
        async def _inner():
            async with WWANClient(bus_type=self._bus_type) as client:
                return await client.send_sms(interface_number, recipient, message)
        return self._run(_inner())

    def list_sms(self, interface_number: int) -> list:
        """List SMS.  See :meth:`WWANClient.list_sms`."""
        return self._run(self._call("list_sms", interface_number))

    def read_sms(self, interface_number: int, message_id: int) -> Dict[str, Any]:
        """Read SMS.  See :meth:`WWANClient.read_sms`."""
        async def _inner():
            async with WWANClient(bus_type=self._bus_type) as client:
                return await client.read_sms(interface_number, message_id)
        return self._run(_inner())

    def delete_sms(self, interface_number: int, message_id: int) -> Dict[str, Any]:
        """Delete SMS.  See :meth:`WWANClient.delete_sms`."""
        async def _inner():
            async with WWANClient(bus_type=self._bus_type) as client:
                return await client.delete_sms(interface_number, message_id)
        return self._run(_inner())

    def delete_all_sms(self, interface_number: int) -> Dict[str, Any]:
        """Delete all SMS.  See :meth:`WWANClient.delete_all_sms`."""
        return self._run(self._call("delete_all_sms", interface_number))

    def wait_for_bearer(
        self,
        interface_number: int,
        target: str = "connected",
        timeout: float = 60.0,
        poll_interval: float = 1.0,
    ) -> bool:
        """Block until bearer reaches *target*.  See :meth:`WWANClient.wait_for_bearer`."""
        async def _inner():
            async with WWANClient(bus_type=self._bus_type) as client:
                return await client.wait_for_bearer(
                    interface_number, target, timeout, poll_interval
                )
        return self._run(_inner())

    def is_connected(self, interface_number: int) -> bool:
        """Check if bearer is up.  See :meth:`WWANClient.is_connected`."""
        return self._run(self._call("is_connected", interface_number))
