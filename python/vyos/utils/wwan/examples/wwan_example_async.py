#!/usr/bin/env python3
# Copyright (C) 2024-2026 IGOS and contributors
# SPDX-License-Identifier: GPL-2.0-or-later
#
# wwan_example_async.py — Async usage examples for WWANClient
#
# Run:  python3 wwan_example_async.py

"""
Async WWAN Client Examples
===========================

Demonstrates every method available on :class:`WWANClient` using
``async / await``.  Requires the WWAN D-Bus service to be running.
"""

import asyncio
import logging
import sys
import os

# Allow imports when running from the examples/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from wwan_client import (  # noqa: E402
    WWANClient,
    WWANError,
    WWANConfigError,
    WWANConnectionError,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

INTERFACE = 0  # wwan0


# ─── 1. Basic connect / status / disconnect ─────────────────────────────────

async def example_basic():
    """Minimal flow: add interface, configure, connect, check status."""

    async with WWANClient() as client:
        # Create (or re-use) the modem interface
        result = await client.add_interface(INTERFACE)
        log.info("add_interface: %s", result)

        # Apply a simple config — connect-on-demand so we control the bearer
        await client.set_configuration(INTERFACE, {
            "connection_mode": "connect-on-demand",
            "primary_sim_slot": 1,
        })
        log.info("Configuration applied")

        # Bring the bearer up
        await client.connect_bearer(INTERFACE)
        log.info("connect_bearer: accepted")

        # Wait until the bearer is actually connected (up to 30 s)
        ok = await client.wait_for_bearer(INTERFACE, "connected", timeout=30)
        log.info("Bearer connected: %s", ok)

        # Quick boolean check
        log.info("is_connected: %s", await client.is_connected(INTERFACE))

        # Full status dump
        status = await client.get_status(INTERFACE)
        for key in ("state", "signal_quality", "operator", "ip_address",
                     "access_technology", "connection_mode"):
            log.info("  %-25s = %s", key, status.get(key, "n/a"))

        # Drop the bearer (modem stays registered, SMS still works)
        await client.disconnect_bearer(INTERFACE)
        log.info("disconnect_bearer: accepted")

        await client.wait_for_bearer(INTERFACE, "disconnected", timeout=15)
        log.info("Bearer disconnected")


# ─── 2. Full configuration example ──────────────────────────────────────────

async def example_full_config():
    """Demonstrate a complete dual-SIM configuration push."""

    config = {
        "connection_mode": "always-on",
        "primary_sim_slot": 1,
        "sim_failover": "enabled",
        "network_mode": "auto",
        "android_apn_discovery": "enabled",

        # SIM slot definitions
        "sim_slots": [
            {
                "slot": 1,
                "enabled": True,
                "apn": {
                    "name": "pda.bell.ca",
                    "username": "",
                    "password": "",
                    "auth_type": "chap",
                },
                "pdp_type": "ipv4v6",
                "roaming": "enabled",
                "pin": "1234",
                "supported_bands": ["all"],
                "data_limit_size": 5_000_000_000,
                "data_limit_action": "disable",
                "data_limit_billing_date": 1,
            },
            {
                "slot": 2,
                "enabled": True,
                "apn": {"name": "backup.apn", "auth_type": "none"},
                "pdp_type": "ipv4",
                "pin": "5678",
                "data_limit_action": "sim-failover",
            },
        ],

        # Enhanced reconnection
        "enhanced_reconnection": {
            "enabled": True,
            "signal_threshold_rssi": -85,
            "signal_threshold_rsrp": -105,
            "retry_interval_good_signal": 30,
            "retry_interval_poor_signal": 120,
        },

        # Connectivity monitoring
        "connectivity_monitoring": {
            "enabled": True,
            "interval": 60,
            "failure_threshold": 2,
            "ipv4_targets": ["8.8.8.8", "1.1.1.1", "9.9.9.9"],
        },

        # Interface management
        "interface_management": {
            "enabled": True,
            "bearer_disconnect_delay": 15,
            "registration_recovery_delay": 20,
        },

        # Hardware reset
        "hardware_reset_enabled": True,
        "max_hardware_resets": 3,

        # Logging
        "verbose_logging": True,
        "log_level": "info",
    }

    async with WWANClient() as client:
        await client.add_interface(INTERFACE)
        result = await client.set_configuration(INTERFACE, config)
        log.info("Full config applied: %s", result)


# ─── 3. Dial-on-demand bearer management ────────────────────────────────────

async def example_dial_on_demand():
    """Show the dial-on-demand workflow: auto-connect → drop → reconnect."""

    async with WWANClient() as client:
        await client.add_interface(INTERFACE)
        await client.set_configuration(INTERFACE, {
            "connection_mode": "dial-on-demand",
            "primary_sim_slot": 1,
        })

        # Bearer comes up automatically — wait for it
        log.info("Waiting for auto-connect…")
        await client.wait_for_bearer(INTERFACE, "connected", timeout=60)
        log.info("Bearer is UP")

        # Application decides data is no longer needed — drop bearer
        await client.disconnect_bearer(INTERFACE)
        await client.wait_for_bearer(INTERFACE, "disconnected", timeout=15)
        log.info("Bearer is DOWN (modem still registered, SMS available)")

        # Later, application needs data again
        await client.connect_bearer(INTERFACE)
        await client.wait_for_bearer(INTERFACE, "connected", timeout=30)
        log.info("Bearer is UP again")


# ─── 4. Status polling loop ─────────────────────────────────────────────────

async def example_status_poll():
    """Poll bearer status every 5 seconds for 30 seconds."""

    async with WWANClient() as client:
        for i in range(6):
            bearer = await client.get_bearer_status(INTERFACE)
            connected = await client.is_connected(INTERFACE)
            log.info("[%2ds]  bearer=%s  is_connected=%s",
                     i * 5, bearer, connected)
            if i < 5:
                await asyncio.sleep(5)


# ─── 5. Error handling ──────────────────────────────────────────────────────

async def example_error_handling():
    """Show how to handle the typed exceptions."""

    async with WWANClient() as client:
        # Bad config — should raise WWANConfigError
        try:
            await client.set_configuration(INTERFACE, {
                "connection_mode": "INVALID_VALUE",
            })
        except WWANConfigError as exc:
            log.warning("Config rejected (expected): %s", exc)

        # Good config
        try:
            await client.set_configuration(INTERFACE, {
                "connection_mode": "always-on",
            })
            log.info("Valid config accepted")
        except WWANConfigError as exc:
            log.error("Unexpected rejection: %s", exc)


# ─── 6. Standalone connect / disconnect ────────────────────────────────────

async def example_standalone():
    """Use the standalone connect()/disconnect() methods."""

    async with WWANClient() as client:
        result = await client.connect(INTERFACE)
        log.info("connect(): %s", result)

        await asyncio.sleep(5)

        result = await client.disconnect(INTERFACE)
        log.info("disconnect(): %s", result)


# ─── main ────────────────────────────────────────────────────────────────────

async def main():
    examples = {
        "basic":          example_basic,
        "full-config":    example_full_config,
        "dial-on-demand": example_dial_on_demand,
        "status-poll":    example_status_poll,
        "error-handling": example_error_handling,
        "standalone":     example_standalone,
    }

    choice = sys.argv[1] if len(sys.argv) > 1 else "basic"

    if choice not in examples:
        print(f"Usage: {sys.argv[0]} [{' | '.join(examples)}]")
        sys.exit(1)

    log.info("Running example: %s", choice)
    try:
        await examples[choice]()
    except WWANConnectionError as exc:
        log.error("D-Bus connection failed — is the service running?  %s", exc)
        sys.exit(1)
    except WWANError as exc:
        log.error("WWAN error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
