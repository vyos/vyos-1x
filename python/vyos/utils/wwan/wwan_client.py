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
import logging
from typing import Any, Dict, Optional

from dbus_next import Variant  # pylint: disable=import-error
from dbus_next.aio import MessageBus  # pylint: disable=import-error
from dbus_next.constants import BusType  # pylint: disable=import-error
from dbus_next.errors import DBusError  # pylint: disable=import-error

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────

BUS_NAME = "com.igos.IgosModemManager"
CONTROL_PATH = "/com/igos/IgosModemManager/Control"
CONTROL_IFACE = "com.igos.IgosModemManager.Control"
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
        # Cache of introspected per-interface proxies: {int: iface_proxy}
        self._iface_cache: Dict[int, Any] = {}

    # ── lifecycle ────────────────────────────────────────────────────────

    async def open(self) -> "WWANClient":
        """Connect to the D-Bus system bus and introspect the Control object."""
        try:
            self._bus = await MessageBus(bus_type=self._bus_type).connect()
            intro = await self._bus.introspect(BUS_NAME, CONTROL_PATH)
            obj = self._bus.get_proxy_object(BUS_NAME, CONTROL_PATH, intro)
            self._ctrl_iface = obj.get_interface(CONTROL_IFACE)
        except Exception as exc:
            raise WWANConnectionError(
                f"Failed to connect to {BUS_NAME}: {exc}"
            ) from exc
        return self

    async def close(self) -> None:
        """Disconnect from the D-Bus bus."""
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
            ``connection_mode``, ``active_sim_slot``, ``sim_failover``,
            ``android_apn_discovery``, ``network_mode``, ``connection_timeout``,
            ``registration_timeout``, ``network_scan_timeout``,
            ``normal_monitoring_interval``, ``system_health_check_interval``,
            ``verbose_logging``, ``log_level``, ``snmp_monitoring``,
            ``detailed_status``, ``hardware_reset_enabled``,
            ``max_hardware_resets``, ``hardware_reset_cooldown``,
            ``data_usage_monitoring_interval``, ``failover``,
            ``failover_connect_retries``, ``failover_revert_timer``,
            ``failover_signal_loss_timer``, ``failover_signal_threshold``,
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
            ``ip_change_delay``, ``ensure_link_up_on_connect``,
            ``monitor_bearer_state``, ``monitor_ip_changes``,
            ``interface_up_timeout``.

            ``sim_slots`` — list of per-SIM dicts, each with:
            ``slot``, ``enabled``, ``apn`` (str or ``{name, username,
            password, auth_type}``), ``pdp_type``, ``roaming``, ``pin``,
            ``puk``, ``supported_bands``,
            ``preferred_carrier``, ``enable_network_scan``,
            ``data_limit_size``, ``data_limit_action``,
            ``data_limit_billing_date``.

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
            ``"connected"`` when Bearer is active (FSM in CONNECTED or
            USAGE_MONITORING), ``"disconnected"`` otherwise.
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
            ``modem_model``, ``modem_imei``, ``signal_percent``,
            ``signal_dbm``, ``access_technology_name``,
            ``operator_name``, ``operator_code``,
            ``registration_state``, ``connection_mode``,
            ``active_sim_slot``, ``configured_sim_slot``,
            ``is_on_failover_sim``, ``sim_imsi``, ``sim_iccid``,
            ``ipv4_address``, ``ipv6_address``, ``ipv4_gateway``,
            ``session_rx_bytes``, ``session_tx_bytes``,
            ``cumulative_bytes``, ``data_usage_percent``,
            ``connected_apn``, ``network_mode``.

            **SIM PIN/PUK unlock status** —
            ``pin_unlock_attempted``, ``pin_unlock_failed``,
            ``puk_unlock_attempted``, ``puk_unlock_failed``,
            ``sim_permanently_locked``,
            ``pin_retries_remaining``, ``puk_retries_remaining``.
        """
        iface = await self._get_iface(interface_number)
        try:
            raw = await iface.call_get_status()
            return _variant_to_python(raw)
        except DBusError as exc:
            raise WWANError(f"GetStatus failed: {exc}") from exc

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

    def get_bearer_status(self, interface_number: int) -> str:
        """Poll bearer state.  See :meth:`WWANClient.get_bearer_status`."""
        return self._run(self._call("get_bearer_status", interface_number))

    def get_status(self, interface_number: int) -> Dict[str, Any]:
        """Full status dict.  See :meth:`WWANClient.get_status`."""
        return self._run(self._call("get_status", interface_number))

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
