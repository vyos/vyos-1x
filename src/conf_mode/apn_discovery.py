"""
WWAN APN Discovery Module

This module provides APN discovery functionality for WWAN connections.
Extracted from the main state machine to improve code organization and maintainability.
Handles Android APN database lookup, fallback discovery, and APN prioritization.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from wwan_utilities import extract_apn_field, convert_android_auth_type, calculate_android_priority

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

        # Fallback APN database for common carriers
        self.fallback_db = {
            "310260": [{"name": "fast.t-mobile.com", "username": "", "password": "", "auth_type": "none", "priority": 1}],
            "311480": [{"name": "vzwinternet", "username": "", "password": "", "auth_type": "none", "priority": 1}],
            "310410": [{"name": "broadband", "username": "", "password": "", "auth_type": "none", "priority": 1}],
            "302720": [{"name": "pda.bell.ca", "username": "", "password": "", "auth_type": "none", "priority": 1}],
            "302610": [
                {"name": "", "username": "", "password": "", "auth_type": "none", "priority": 1},
                {"name": "nxtgenphone", "username": "", "password": "", "auth_type": "none", "priority": 2},
                {"name": "pda.bell.ca", "username": "", "password": "", "auth_type": "none", "priority": 3},
                {"name": "bell.com", "username": "", "password": "", "auth_type": "none", "priority": 4}
            ],
            "302880": [{"name": "internet.com", "username": "", "password": "", "auth_type": "none", "priority": 1}],
        }

    async def discover_apn_candidates(self, sim_info: Dict[str, Any], sim_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Discover APN candidates using Android library or fallback"""
        try:
            if APN_LOOKUP_AVAILABLE:
                return await self._discover_with_android_library(sim_info, sim_config)
            else:
                return await self._discover_with_fallback(sim_info, sim_config)

        except Exception as e:
            self.logger.error(f"APN discovery failed: {e}",
                            extra={'interface_number': self.interface_number})
            return []

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
            # Fallback to built-in database
            return await self._discover_with_fallback(sim_info, sim_config)

    def _convert_android_apns(self, android_apns: List[Any], sim_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert Android APN format to our standardized format"""
        candidates = []

        for i, apn in enumerate(android_apns):
            try:
                # Android APNs typically have these fields (adjust based on actual structure)
                candidate = {
                    'name': extract_apn_field(apn, 'apn', f'apn_{i}'),
                    'username': extract_apn_field(apn, 'user', ''),
                    'password': extract_apn_field(apn, 'password', ''),
                    'auth_type': convert_android_auth_type(
                        extract_apn_field(apn, 'authtype', '0')
                    ),
                    'type': extract_apn_field(apn, 'type', 'default'),
                    'priority': calculate_android_priority(apn, i),
                    'carrier': sim_info['operator_name'],
                    'mcc_mnc': sim_info['mcc_mnc'],
                    'match_type': 'android_lookup',
                    'source': 'AOSP'
                }

                # Only add if APN name is valid
                if candidate['name'] and candidate['name'] != f'apn_{i}':
                    candidates.append(candidate)

            except Exception as e:
                self.logger.warning(f"Failed to convert Android APN {i}: {e}",
                                  extra={'interface_number': self.interface_number})
                continue

        return candidates

    async def _discover_with_fallback(self, sim_info: Dict[str, Any], sim_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fallback discovery when Android library is not available"""
        self.logger.info("Using fallback APN discovery",
                       extra={'interface_number': self.interface_number,
                              'mcc_mnc': sim_info['mcc_mnc'],
                              'operator_name': sim_info['operator_name']})

        candidates = []

        mcc_mnc = sim_info['mcc_mnc']
        if mcc_mnc in self.fallback_db:
            for apn in self.fallback_db[mcc_mnc]:
                candidates.append({
                    **apn,
                    'carrier': sim_info['operator_name'],
                    'mcc_mnc': mcc_mnc,
                    'match_type': 'fallback_database',
                    'source': 'builtin'
                })

        return candidates

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
        """Update fallback database with successful APN for future use"""
        try:
            if mcc_mnc not in self.fallback_db:
                self.fallback_db[mcc_mnc] = []

            # Add to fallback database if not already present
            apn_name = apn_config.get('name')
            existing_names = [apn.get('name') for apn in self.fallback_db[mcc_mnc]]

            if apn_name and apn_name not in existing_names:
                fallback_entry = {
                    'name': apn_name,
                    'username': apn_config.get('username', ''),
                    'password': apn_config.get('password', ''),
                    'auth_type': apn_config.get('auth_type', 'none'),
                    'priority': 1
                }

                self.fallback_db[mcc_mnc].insert(0, fallback_entry)  # Add as highest priority

                self.logger.info(f"Updated fallback database with successful APN: {apn_name}",
                               extra={'interface_number': self.interface_number,
                                      'mcc_mnc': mcc_mnc})

        except Exception as e:
            self.logger.warning(f"Failed to update fallback database: {e}",
                              extra={'interface_number': self.interface_number})