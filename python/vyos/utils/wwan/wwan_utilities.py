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

"""
WWAN Utilities Module
Extracted utility functions for APN processing and conversions
"""

from typing import Any, Dict, List
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# APN PROCESSING UTILITIES
# ============================================================================

def extract_apn_field(apn: Any, field_name: str, default_value: str = '') -> str:
    """
    Extract field from Android APN object (adjust based on actual structure)

    Args:
        apn: Android APN object (dict, object, or other)
        field_name: Name of field to extract
        default_value: Default value if field not found

    Returns:
        Extracted field value as string
    """
    try:
        # Handle different possible structures
        if hasattr(apn, field_name):
            return str(getattr(apn, field_name, default_value))
        elif isinstance(apn, dict):
            return str(apn.get(field_name, default_value))
        elif hasattr(apn, '__getitem__'):
            return str(apn[field_name]) if field_name in apn else default_value
        else:
            return default_value
    except (AttributeError, KeyError, TypeError):
        return default_value

def convert_android_auth_type(android_auth: str) -> str:
    """
    Convert Android auth type to our format

    Args:
        android_auth: Android authentication type (string or numeric)

    Returns:
        Standardized auth type string
    """
    auth_mapping = {
        '0': 'none',      # No authentication
        '1': 'pap',       # PAP
        '2': 'chap',      # CHAP
        '3': 'pap-chap',  # PAP or CHAP
        'none': 'none',
        'pap': 'pap',
        'chap': 'chap',
        'pap-chap': 'pap-chap'
    }
    return auth_mapping.get(str(android_auth).lower(), 'none')

def calculate_android_priority(apn: Dict, index: int) -> int:
    """
    Calculate priority from Android APN (lower = higher priority)

    Args:
        apn: Android APN dictionary
        index: Index in the APN list

    Returns:
        Priority value (lower = higher priority)
    """
    try:
        # Check for explicit priority
        explicit_priority = extract_apn_field(apn, 'priority', None)
        if explicit_priority and explicit_priority.isdigit():
            return int(explicit_priority)

        # Calculate priority based on APN type and position
        apn_type = extract_apn_field(apn, 'type', 'default').lower()

        # Priority based on type relevance
        if isinstance(apn_type, list):
            apn_types = [t.lower() for t in apn_type]
        else:
            apn_types = [t.lower() for t in str(apn_type).split(',')]

        base_priority = 100  # Default priority

        # Higher priority for more important types
        if 'default' in apn_types:
            base_priority -= 50
        if 'internet' in apn_types:
            base_priority -= 30
        if 'ia' in apn_types:  # Initial Attach
            base_priority -= 20
        if 'supl' in apn_types or 'mms' in apn_types:
            base_priority += 20  # Lower priority for specialized services

        # Add index to break ties (earlier = higher priority)
        return base_priority + index

    except Exception as e:
        logger.debug(f"Priority calculation failed: {e}")
        return 100 + index  # Fallback priority

def convert_android_apns(android_apns: List[Dict], sim_info: Dict) -> List[Dict]:
    """
    Convert Android APN format to our standardized format

    Args:
        android_apns: List of Android APN dictionaries
        sim_info: SIM information dictionary

    Returns:
        List of converted APN candidates
    """
    candidates = []

    for i, apn in enumerate(android_apns):
        try:
            # Convert Android APN to our format
            candidate = {
                'name': extract_apn_field(apn, 'apn', f'apn_{i}'),
                'username': extract_apn_field(apn, 'user', ''),
                'password': extract_apn_field(apn, 'password', ''),
                'auth_type': convert_android_auth_type(
                    extract_apn_field(apn, 'authtype', '0')
                ),
                'type': extract_apn_field(apn, 'type', 'default'),
                'priority': calculate_android_priority(apn, i),
                'carrier': sim_info.get('operator_name', 'Unknown'),
                'mcc_mnc': sim_info.get('mcc_mnc', ''),
                'match_type': 'android_lookup',
                'source': 'AOSP'
            }

            # Only add if APN name is valid
            if candidate['name'] and candidate['name'] != f'apn_{i}':
                candidates.append(candidate)

                logger.debug(f"Converted Android APN: {candidate['name']}, "
                           f"type: {candidate['type']}, "
                           f"priority: {candidate['priority']}")

            else:
                logger.debug(f"Skipping Android APN {i} - invalid name: {candidate['name']}")

        except Exception as e:
            logger.error(f"Failed to convert Android APN {i}: {e}")

    # Sort by priority (lower = higher priority)
    candidates.sort(key=lambda x: x['priority'])

    logger.info(f"Converted {len(candidates)} Android APNs from {len(android_apns)} candidates")
    return candidates

# ============================================================================
# AUTHENTICATION TYPE UTILITIES
# ============================================================================

def normalize_auth_type(auth_type: str) -> str:
    """
    Normalize authentication type to standard format

    Args:
        auth_type: Input authentication type

    Returns:
        Normalized auth type string
    """
    if not auth_type:
        return 'none'

    auth_type = str(auth_type).lower().strip()

    # Direct mappings
    auth_mappings = {
        'none': 'none',
        'pap': 'pap',
        'chap': 'chap',
        'pap-chap': 'pap-chap',
        'both': 'pap-chap',
        'auto': 'pap-chap',
        '0': 'none',
        '1': 'pap',
        '2': 'chap',
        '3': 'pap-chap'
    }

    return auth_mappings.get(auth_type, 'none')

def normalize_pdp_type(pdp_type: str) -> str:
    """
    Normalize PDP/IP type to standard format

    Args:
        pdp_type: Input PDP type

    Returns:
        Normalized PDP type string
    """
    if not pdp_type:
        return 'ipv4'

    pdp_type = str(pdp_type).lower().strip()

    pdp_mappings = {
        'ipv4': 'ipv4',
        'ipv6': 'ipv6',
        'ipv4v6': 'ipv4v6',
        'ip': 'ipv4',
        'ipv4+ipv6': 'ipv4v6',
        'dual': 'ipv4v6',
        'both': 'ipv4v6'
    }

    return pdp_mappings.get(pdp_type, 'ipv4')

# ============================================================================
# MODULE TESTING
# ============================================================================

if __name__ == "__main__":
    # Test the utility functions
    print("=== WWAN Utilities Test ===")

    # Test APN field extraction
    test_apn = {'apn': 'test.apn', 'authtype': '2', 'type': ['default', 'internet']}
    print(f"APN name: {extract_apn_field(test_apn, 'apn')}")
    print(f"Auth type: {convert_android_auth_type(extract_apn_field(test_apn, 'authtype'))}")
    print(f"Priority: {calculate_android_priority(test_apn, 0)}")

    # Test conversions
    test_sim_info = {'operator_name': 'Test Carrier', 'mcc_mnc': '12345'}
    converted = convert_android_apns([test_apn], test_sim_info)
    print(f"Converted APNs: {len(converted)}")
    if converted:
        print(f"First APN: {converted[0]}")
