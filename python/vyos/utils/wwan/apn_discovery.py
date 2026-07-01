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
WWAN APN Discovery Module

This module provides APN discovery functionality for WWAN connections.
Extracted from the main state machine to improve code organization and maintainability.
Handles Android APN database lookup, fallback discovery, and APN prioritization.
"""

import logging
import asyncio
from typing import Dict, List, Any

from vyos.utils.wwan.wwan_utilities import convert_android_apns

logger = logging.getLogger(__name__)

# Check if Android APN lookup is available
try:
    from apnscripts.apn_lookup_run import find_apn_list
    APN_LOOKUP_AVAILABLE = True
except ImportError:
    APN_LOOKUP_AVAILABLE = False
    logger.warning("Android APN lookup library not available, using fallback only")


class APNDiscovery:
    """
    Handles APN discovery using Android APN database and fallback methods.

    Extracted from the state machine to provide clean separation of concerns
    for APN discovery functionality.
    """

    def __init__(self, interface_number: int):
        self.interface_number = interface_number
        self.logger = logging.getLogger(f"{__name__}.Interface{interface_number}")

    @staticmethod
    def _blank_apn_candidate(sim_info: Dict[str, Any]) -> Dict[str, Any]:
        """Build the carrier-agnostic blank-APN candidate.

        Many modern carriers (3GPP-compliant) auto-assign an APN when the
        attach request carries an empty APN field.  This is universal,
        carrier-neutral behavior — not a hardcoded guess — and serves as
        the last-resort candidate when no other discovery path produced
        results.
        """
        return {
            'name': '',
            'username': '',
            'password': '',
            'auth_type': 'none',
            'priority': 99,
            'carrier': sim_info.get('operator_name') or '',
            'mcc_mnc': sim_info.get('mcc_mnc') or '',
            'match_type': 'blank_apn',
            'source': 'carrier_assigned',
        }

    async def discover_apn_candidates(self, sim_info: Dict[str, Any], sim_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Discover APN candidates.

        Strategy (no hardcoded carrier-to-APN table):
          1. Query the Android APN library if available.
          2. Always append a blank-APN last-resort candidate, allowing the
             carrier to auto-assign the APN per 3GPP attach semantics.

        The user-configured APN (``set interfaces wwan wwanN sim slot N
        apn ...``) is handled by the caller and takes precedence over
        anything returned here.
        """
        candidates: List[Dict[str, Any]] = []

        if APN_LOOKUP_AVAILABLE:
            try:
                candidates = await self._discover_with_android_library(
                    sim_info, sim_config
                )
            except Exception as e:
                self.logger.error(f"APN discovery failed: {e}",
                                extra={'interface_number': self.interface_number})
                candidates = []
        else:
            self.logger.info(
                "Android APN library unavailable — using blank-APN "
                "carrier auto-assignment as the only candidate",
                extra={'interface_number': self.interface_number,
                       'mcc_mnc': sim_info.get('mcc_mnc')})

        # Always append a blank-APN last-resort candidate (carrier-assigned).
        # Skip if a blank entry was already discovered to avoid duplicates.
        if not any(not c.get('name') for c in candidates):
            candidates.append(self._blank_apn_candidate(sim_info))

        return candidates

    async def _discover_with_android_library(self, sim_info: Dict[str, Any], sim_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Use the Android apnscripts library for APN discovery"""
        try:
            # Extract SIM identifiers for the Android library
            mcc_mnc = sim_info['mcc_mnc'] or ""
            imsi_prefix = sim_info['imsi'][:15] if sim_info['imsi'] else ""
            iccid_prefix = sim_info['sim_identifier'] or ""
            gid1 = sim_info['gid1'] or ""
            gid2 = sim_info['gid2'] or ""
            plmn = sim_info['plmn'] or ""
            spn = sim_info['spn'] or ""

            self.logger.info("Calling Android APN lookup",
                           extra={'interface_number': self.interface_number,
                                  'mcc_mnc': mcc_mnc,
                                  'imsi_prefix': imsi_prefix[:6] + '...' if imsi_prefix else None,
                                  'plmn': plmn,
                                  'spn': spn})

            # Call the Android lookup library in executor to avoid blocking
            loop = asyncio.get_event_loop()
            apn_list = await loop.run_in_executor(
                None,
                find_apn_list,
                mcc_mnc, imsi_prefix, iccid_prefix, gid1, gid2, plmn, spn
            )

            self.logger.info("Android APN lookup completed",
                           extra={'interface_number': self.interface_number,
                                  'raw_apn_count': len(apn_list),
                                  'mcc_mnc': mcc_mnc})

            # Convert Android APNs to our format
            candidates = self._convert_android_apns(apn_list, sim_info)

            return candidates

        except Exception as e:
            self.logger.error(f"Android APN lookup failed: {e}",
                            extra={'interface_number': self.interface_number})
            return []

    def _convert_android_apns(self, android_apns: List[Any], sim_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert Android APN format to our standardized format.

        Delegates to the shared convert_android_apns() in wwan_utilities to
        avoid divergent duplicate implementations.
        """
        return convert_android_apns(android_apns, sim_info)

    async def _discover_with_fallback(self, sim_info: Dict[str, Any], sim_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Removed: hardcoded fallback APN database is no longer supported.

        Production deployments must rely on the Android APN library
        (``apnscripts``) or an explicit user-configured APN.
        """
        self.logger.warning(
            "_discover_with_fallback() called — hardcoded fallback DB "
            "removed; returning no candidates",
            extra={'interface_number': self.interface_number})
        return []

    def prioritize_apn_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort APN candidates by priority (lower number = higher priority)"""
        if not candidates:
            return candidates

        try:
            # Sort by priority, then by name for consistent ordering
            sorted_candidates = sorted(
                candidates,
                key=lambda x: (x.get('priority', 99), x.get('name', ''))
            )

            self.logger.info(f"Prioritized {len(sorted_candidates)} APN candidates",
                           extra={'interface_number': self.interface_number,
                                  'top_candidate': sorted_candidates[0].get('name') if sorted_candidates else None})

            return sorted_candidates

        except Exception as e:
            self.logger.warning(f"Failed to prioritize APN candidates: {e}",
                              extra={'interface_number': self.interface_number})
            return candidates

    def validate_apn_candidate(self, candidate: Dict[str, Any]) -> bool:
        """Validate that an APN candidate has required fields"""
        try:
            # Check required fields
            if not candidate.get('name'):
                return False

            # Check auth type is valid
            valid_auth_types = ['none', 'pap', 'chap', 'pap-chap']
            if candidate.get('auth_type') not in valid_auth_types:
                self.logger.warning(f"Invalid auth_type '{candidate.get('auth_type')}' for APN {candidate.get('name')}",
                                  extra={'interface_number': self.interface_number})
                return False

            return True

        except Exception as e:
            self.logger.warning(f"APN candidate validation failed: {e}",
                              extra={'interface_number': self.interface_number})
            return False

    def get_apn_summary(self, candidate: Dict[str, Any]) -> str:
        """Get a human-readable summary of an APN candidate"""
        try:
            name = candidate.get('name', 'unknown')
            carrier = candidate.get('carrier', 'unknown')
            auth = candidate.get('auth_type', 'none')
            priority = candidate.get('priority', 'unknown')
            source = candidate.get('source', 'unknown')

            return f"{name} ({carrier}, auth:{auth}, priority:{priority}, source:{source})"

        except Exception as e:
            return f"APN summary error: {e}"

    def update_fallback_database(self, mcc_mnc: str, apn_config: Dict[str, Any]):
        """Removed: hardcoded fallback APN database is no longer maintained.

        Successful APNs are tracked elsewhere (per-SIM config); no in-memory
        carrier-to-APN table is updated.  Kept as a no-op stub for backward
        compatibility with any external caller.
        """
        return
