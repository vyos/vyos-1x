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

"""
WWAN Connection Management Module

This module provides connection management functionality for WWAN interfaces.
Extracted from the main state machine to improve code organization and maintainability.
Handles connection attempts, bearer management, and APN configuration.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from dbus_next import Variant  # pylint: disable=import-error

logger = logging.getLogger(__name__)

# D-Bus interfaces
SIMPLE_INTERFACE = 'org.freedesktop.ModemManager1.Modem.Simple'
BEARER_INTERFACE = 'org.freedesktop.ModemManager1.Bearer'


class ConnectionManager:
    """
    Handles WWAN connection management including APN attempts, bearer management,
    and network interface configuration.

    Extracted from the state machine to provide clean separation of concerns
    for connection management functionality.
    """

    def __init__(self, interface_number: int):
        self.interface_number = interface_number
        self.logger = logging.getLogger(f"{__name__}.Interface{interface_number}")
        self.bearer_path = None
        self.connected_apn = None  # Store last successful APN config dict

    def set_proxy(self, proxy):
        """Set the D-Bus proxy for modem operations"""
        self.proxy = proxy

    async def try_apn_candidates(self, candidates: List[Dict[str, Any]], sim_config: Dict[str, Any], sim_info: Dict[str, Any]) -> tuple[bool, str]:
        """Try APN candidates in priority order.

        Returns:
            (success: bool, reason: str) — reason is 'success', 'all_apn_failed',
            'restart_required' (non-APN modem failure), or 'connection_failed'.

        Note: The state machine drives APN iteration via its own canonical loop
        (_try_apn_candidates).  This method is retained for external / test callers
        that still invoke ConnectionManager directly.
        """
        self.logger.info("Trying APN candidates in priority order",
                       extra={'interface_number': self.interface_number,
                              'candidate_count': len(candidates)})

        for i, candidate in enumerate(candidates):
            try:
                self.logger.info(f"Trying APN candidate {i+1}/{len(candidates)}",
                               extra={'interface_number': self.interface_number,
                                      'apn_name': candidate['name'],
                                      'apn_type': candidate.get('type', 'default'),
                                      'priority': candidate.get('priority', 0)})

                # Convert candidate to our APN config format
                apn_config = {
                    'name': candidate['name'],
                    'username': candidate.get('username', ''),
                    'password': candidate.get('password', ''),
                    'auth_type': candidate.get('auth_type', 'none')
                }

                success, reason = await self.try_connection_with_apn(apn_config, sim_config)

                if success:
                    self.logger.info("APN candidate connection successful",
                                   extra={'interface_number': self.interface_number,
                                          'successful_apn': candidate['name'],
                                          'attempt_number': i+1,
                                          'total_attempts': len(candidates)})
                    return (True, 'success')

                # Non-APN modem/network failure: stop immediately and ask caller
                # to restart the connection workflow rather than burning remaining APNs.
                if reason == 'connection_failed':
                    self.logger.warning("Non-APN failure while testing candidate; aborting cascade",
                                       extra={'interface_number': self.interface_number,
                                              'failed_apn': candidate['name'],
                                              'failure_reason': reason})
                    return (False, 'restart_required')

                self.logger.info(f"APN candidate {i+1} failed ({reason}), trying next",
                               extra={'interface_number': self.interface_number,
                                      'failed_apn': candidate['name'],
                                      'remaining_candidates': len(candidates) - i - 1})

            except Exception as e:
                self.logger.warning(f"Error trying APN candidate: {e}",
                                  extra={'interface_number': self.interface_number,
                                         'apn_name': candidate['name']})
                continue

        # All candidates exhausted without a terminal modem failure.
        self.logger.warning("All APN candidates failed",
                          extra={'interface_number': self.interface_number,
                                 'total_candidates_tried': len(candidates)})
        return (False, 'all_apn_failed')

    async def try_connection_with_apn(self, apn_config: Dict[str, Any], sim_config: Dict[str, Any]) -> tuple[bool, str]:
        """Try to establish connection with specific APN configuration.

        Returns:
            (success: bool, reason: str) where reason is one of:
            - "success": connection established and verified
            - "apn_rejected": ModemManager explicitly rejected this APN (move to next APN)
            - "connection_failed": connect failed for non-APN reason (restart connection process)
            - "timeout": ModemManager didn't respond in time (check state to see if hung)
            - "verification_failed": bearer created but not actually connected
            - "error": unexpected error during attempt
        """
        try:
            apn_config = self._normalize_apn_config(apn_config)
            connection_timeout = float(sim_config.get('connection_timeout', 60.0))
            # Keep a sane lower bound for non-VyOS callers/tests.
            if connection_timeout < 5.0:
                connection_timeout = 5.0

            self.logger.info("Attempting connection with APN",
                           extra={'interface_number': self.interface_number,
                                  'apn_name': apn_config['name'],
                                  'has_auth': apn_config['auth_type'] != 'none',
                                  'timeout_seconds': connection_timeout})

            # Build connection parameters
            connect_params = {}

            # Add APN name
            connect_params['apn'] = Variant('s', apn_config['name'])

            # Add PDP/IP type
            pdp_type = sim_config.get('pdp_type', 'ipv4')
            connect_params['ip-type'] = Variant('u', self._convert_pdp_type(pdp_type))

            # Add authentication if configured
            if apn_config['auth_type'] != 'none' and apn_config['username']:
                connect_params['user'] = Variant('s', apn_config['username'])
                connect_params['password'] = Variant('s', apn_config['password'])
                connect_params['allowed-auth'] = Variant('u', self._convert_auth_type(apn_config['auth_type']))

            # Add roaming settings
            roaming = sim_config.get('roaming', 'disabled')
            connect_params['allow-roaming'] = Variant('b', roaming == 'enabled')

            # Attempt connection with timeout
            simple_iface = self.proxy.get_interface(SIMPLE_INTERFACE)

            try:
                bearer_path = await asyncio.wait_for(
                    simple_iface.call_connect(connect_params),
                    timeout=connection_timeout
                )

                self.bearer_path = bearer_path

                # Verify connection
                await asyncio.sleep(3)  # Brief wait for connection to establish
                is_connected = await self._verify_bearer_connection()

                if is_connected:
                    self.logger.info("APN connection successful and verified",
                                   extra={'interface_number': self.interface_number,
                                          'apn_name': apn_config['name'],
                                          'bearer_path': bearer_path})
                    self.connected_apn = apn_config.copy()
                    return (True, "success")
                else:
                    self.logger.warning("APN connection created but verification failed",
                                      extra={'interface_number': self.interface_number,
                                             'apn_name': apn_config['name']})

                    # Cleanup failed connection
                    await self._cleanup_failed_bearer()
                    return (False, "verification_failed")

            except asyncio.TimeoutError:
                self.logger.warning("APN connection attempt timed out (MM may still be trying)",
                                  extra={'interface_number': self.interface_number,
                                         'apn_name': apn_config['name'],
                                         'timeout_seconds': connection_timeout})
                # Timeout does NOT mean APN was rejected — MM may still be negotiating.
                # Caller should check MM state to see if it's still CONNECTING.
                # A bearer may have been partially created before the timeout.
                # Attempt cleanup to avoid leaked bearers on the modem.
                await self._cleanup_failed_bearer()
                return (False, "timeout")

            except Exception as e:
                rejection_class = self._classify_connect_failure(e)
                if rejection_class == 'apn_rejected':
                    self.logger.error(f"ModemManager rejected APN: {e}",
                                    extra={'interface_number': self.interface_number,
                                           'apn_name': apn_config.get('name', 'unknown'),
                                           'failure_class': rejection_class})
                else:
                    self.logger.error(f"ModemManager connect failed (non-APN): {e}",
                                    extra={'interface_number': self.interface_number,
                                           'apn_name': apn_config.get('name', 'unknown'),
                                           'failure_class': rejection_class})
                # Clean up any partial bearer from MM's attempt
                await self._cleanup_failed_bearer()
                return (False, rejection_class)

        except Exception as e:
            self.logger.error(f"Unexpected error during APN connection: {e}",
                            extra={'interface_number': self.interface_number,
                                   'apn_name': apn_config.get('name', 'unknown')})
            return (False, "error")

    @staticmethod
    def _classify_connect_failure(exc: Exception) -> str:
        """Classify ModemManager connect failure into APN vs non-APN causes.

        Returns one of:
          - "apn_rejected": likely APN/auth/profile specific rejection
          - "connection_failed": modem/network/MM state failure (restart flow)
        """
        text = str(exc).lower()

        # APN/profile-specific failures should advance to next APN candidate.
        apn_related_markers = [
            'apn',
            'authentication',
            'auth',
            'username',
            'password',
            'pdp',
            'pdn',
            'user authentication',
        ]

        # Non-APN failures should restart the whole connection process.
        non_apn_markers = [
            'roaming',
            'not allowed',
            'no service',
            'no network',
            'network timeout',
            'sim',
            'modem',
            'busy',
            'in progress',
            'operation not allowed',
            'wrong state',
            'powered off',
            'disabled',
            'not registered',
        ]

        if any(marker in text for marker in non_apn_markers):
            return 'connection_failed'
        if any(marker in text for marker in apn_related_markers):
            return 'apn_rejected'

        # Unknown MM errors are safer to treat as non-APN infrastructure failures.
        return 'connection_failed'

    def _normalize_apn_config(self, apn_config: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize APN config and flatten nested config structures."""
        if not isinstance(apn_config, dict):
            return {
                'name': str(apn_config or ''),
                'username': '',
                'password': '',
                'auth_type': 'none'
            }

        # Some callers may pass nested APN config in the ``name`` field.
        nested_apn = apn_config.get('name')
        if isinstance(nested_apn, dict):
            apn_config = {
                **nested_apn,
                'username': nested_apn.get('username', apn_config.get('username', '')),
                'password': nested_apn.get('password', apn_config.get('password', '')),
                'auth_type': nested_apn.get('auth_type', apn_config.get('auth_type', 'none')),
            }

        return {
            'name': str(apn_config.get('name', '') or ''),
            'username': str(apn_config.get('username', '') or ''),
            'password': str(apn_config.get('password', '') or ''),
            'auth_type': str(apn_config.get('auth_type', 'none') or 'none')
        }

    async def _verify_bearer_connection(self) -> bool:
        """Verify that the bearer connection is actually working"""
        try:
            if not self.bearer_path:
                return False

            # Get bearer interface
            introspect = await self.proxy.bus.introspect('org.freedesktop.ModemManager1', self.bearer_path)
            bearer_proxy = self.proxy.bus.get_proxy_object(
                'org.freedesktop.ModemManager1',
                self.bearer_path,
                introspect
            )
            bearer_iface = bearer_proxy.get_interface(BEARER_INTERFACE)

            # Check bearer connection status
            connected = await bearer_iface.get_connected()

            if connected:
                # Get IP configuration if available
                ip_config = await bearer_iface.get_ip4_config()
                if ip_config:
                    self.logger.debug("Bearer connection verified with IP config",
                                    extra={'interface_number': self.interface_number,
                                           'bearer_path': self.bearer_path})
                    return True

            return False

        except Exception as e:
            self.logger.warning(f"Bearer verification failed: {e}",
                              extra={'interface_number': self.interface_number})
            return False

    async def _cleanup_failed_bearer(self):
        """Clean up a failed bearer connection"""
        try:
            if not self.bearer_path:
                return

            # Try to disconnect the bearer
            simple_iface = self.proxy.get_interface(SIMPLE_INTERFACE)
            await simple_iface.call_disconnect(self.bearer_path)

            self.logger.debug("Cleaned up failed bearer",
                            extra={'interface_number': self.interface_number,
                                   'bearer_path': self.bearer_path})

        except Exception as e:
            self.logger.debug(f"Failed to cleanup bearer: {e}",
                            extra={'interface_number': self.interface_number})
        finally:
            self.bearer_path = None

    async def disconnect_current_bearer(self) -> bool:
        """Disconnect the current bearer connection"""
        try:
            if not self.bearer_path:
                self.logger.debug("No bearer to disconnect",
                                extra={'interface_number': self.interface_number})
                return True

            simple_iface = self.proxy.get_interface(SIMPLE_INTERFACE)
            await simple_iface.call_disconnect(self.bearer_path)

            self.logger.info("Bearer disconnected successfully",
                           extra={'interface_number': self.interface_number,
                                  'bearer_path': self.bearer_path})

            self.bearer_path = None
            return True

        except Exception as e:
            self.logger.error(f"Failed to disconnect bearer: {e}",
                            extra={'interface_number': self.interface_number})
            return False

    def _convert_pdp_type(self, pdp_type: str) -> int:
        """Convert PDP type string to ModemManager enum value"""
        pdp_mapping = {
            'ipv4': 1,      # MM_BEARER_IP_FAMILY_IPV4
            'ipv6': 2,      # MM_BEARER_IP_FAMILY_IPV6
            'ipv4v6': 3,    # MM_BEARER_IP_FAMILY_IPV4V6
        }
        return pdp_mapping.get(pdp_type.lower(), 1)  # Default to IPv4

    def _convert_auth_type(self, auth_type: str) -> int:
        """Convert auth type string to ModemManager enum value"""
        auth_mapping = {
            'none': 0,      # MM_BEARER_ALLOWED_AUTH_NONE
            'pap': 1,       # MM_BEARER_ALLOWED_AUTH_PAP
            'chap': 2,      # MM_BEARER_ALLOWED_AUTH_CHAP
            'pap-chap': 3,  # MM_BEARER_ALLOWED_AUTH_PAP | MM_BEARER_ALLOWED_AUTH_CHAP
        }
        return auth_mapping.get(auth_type.lower(), 0)  # Default to none



    def get_current_bearer_path(self) -> Optional[str]:
        """Get the current bearer path"""
        return self.bearer_path

    def is_connected(self) -> bool:
        """Check if there's an active bearer connection"""
        return self.bearer_path is not None

    async def get_connection_info(self) -> Optional[Dict[str, Any]]:
        """Get detailed information about the current connection"""
        try:
            if not self.bearer_path:
                return None

            # Get bearer interface
            introspect = await self.proxy.bus.introspect('org.freedesktop.ModemManager1', self.bearer_path)
            bearer_proxy = self.proxy.bus.get_proxy_object(
                'org.freedesktop.ModemManager1',
                self.bearer_path,
                introspect
            )
            bearer_iface = bearer_proxy.get_interface(BEARER_INTERFACE)

            # Get connection details
            connected = await bearer_iface.get_connected()
            ip_config = await bearer_iface.get_ip4_config() if connected else None

            connection_info = {
                'bearer_path': self.bearer_path,
                'connected': connected,
                'ip_config': ip_config,
                'interface_number': self.interface_number
            }

            return connection_info

        except Exception as e:
            self.logger.warning(f"Failed to get connection info: {e}",
                              extra={'interface_number': self.interface_number})
            return None

    async def monitor_connection_health(self) -> bool:
        """Monitor the health of the current connection"""
        try:
            if not self.bearer_path:
                return False

            connection_info = await self.get_connection_info()

            if connection_info and connection_info.get('connected'):
                self.logger.debug("Connection health check passed",
                                extra={'interface_number': self.interface_number})
                return True
            else:
                self.logger.warning("Connection health check failed",
                                  extra={'interface_number': self.interface_number})
                return False

        except Exception as e:
            self.logger.warning(f"Connection health check error: {e}",
                              extra={'interface_number': self.interface_number})
            return False
