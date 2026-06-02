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

'''
WWAN Configuration Management Module

This module provides configuration loading and validation for the WWAN state machine.
Extracted from the main state machine to improve code organization and maintainability.
'''

import logging
from typing import Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EnhancedReconnectionConfig:
    '''Enhanced reconnection strategy configuration'''
    enabled: bool = True
    signal_threshold: int = -85
    max_retries: int = 3
    retry_interval_good_signal: int = 30
    retry_interval_poor_signal: int = 120
    max_wait_for_signal: int = 120
    signal_check_interval: int = 10
    normal_monitoring_interval: int = 30
    signal_strength_buffer: int = 5


@dataclass
class InterfaceManagementConfig:
    '''Network interface management configuration'''
    enabled: bool = True
    bearer_disconnect_delay: int = 15
    registration_recovery_delay: int = 20
    registration_flap_count: int = 5
    registration_flap_window: int = 360
    ip_change_delay: int = 500
    ensure_link_up_on_connect: bool = True
    monitor_bearer_state: bool = True
    monitor_ip_changes: bool = True
    interface_up_timeout: int = 10


@dataclass
class FailedRetryConfig:
    '''Failed-state periodic retry configuration'''
    enabled: bool = True
    intervals: list = None  # Backoff intervals in seconds, e.g. [600, 1800, 3600, 7200]
    max_interval: int = 7200  # Cap once intervals list is exhausted (2 hr, carrier-friendly)
    escalation_threshold: int = 3  # After N consecutive failures, escalate to disable/enable cycle (0 = never)

    def __post_init__(self):
        if self.intervals is None:
            self.intervals = [600, 1800, 3600, 7200]


@dataclass
class WWANConfiguration:
    '''Complete WWAN configuration structure'''
    primary_sim_slot: int = 1
    enhanced_reconnection: EnhancedReconnectionConfig = None
    interface_management: InterfaceManagementConfig = None
    failed_retry: FailedRetryConfig = None
    connectivity_monitoring: Dict[str, Any] = None
    raw_config: Dict[str, Any] = None

    def __post_init__(self):
        if self.enhanced_reconnection is None:
            self.enhanced_reconnection = EnhancedReconnectionConfig()
        if self.interface_management is None:
            self.interface_management = InterfaceManagementConfig()
        if self.failed_retry is None:
            self.failed_retry = FailedRetryConfig()
        if self.connectivity_monitoring is None:
            self.connectivity_monitoring = {}


class ConfigurationLoader:
    '''
    Handles loading and parsing WWAN configuration.

    Extracted from the monster apply_config method to improve code organization.
    Provides safe configuration loading with validation and normalization.
    '''

    def __init__(self, interface_number: int):
        self.interface_number = interface_number
        self.logger = logging.getLogger(f"{__name__}.Interface{interface_number}")

    def load_configuration(self, config: Dict[str, Any]) -> WWANConfiguration:
        '''
        Load and parse WWAN configuration from raw config dictionary.

        Args:
            config: Raw configuration dictionary

        Returns:
            WWANConfiguration: Parsed and validated configuration
        '''
        try:
            self.logger.info('Loading WWAN configuration',
                           extra={'interface_number': self.interface_number,
                                  'config_keys': list(config.keys()) if config else []})

            # Parse enhanced reconnection configuration
            enhanced_reconnection = self._parse_enhanced_reconnection_config(config)

            # Parse interface management configuration
            interface_management = self._parse_interface_management_config(config)

            # Parse connectivity monitoring configuration
            connectivity_monitoring = self._parse_connectivity_monitoring_config(config)

            # Parse failed-state retry configuration
            failed_retry = self._parse_failed_retry_config(config)

            # Get primary SIM slot
            primary_sim_slot = config.get('primary_sim_slot', 1)

            # Create complete configuration
            wwan_config = WWANConfiguration(
                primary_sim_slot=primary_sim_slot,
                enhanced_reconnection=enhanced_reconnection,
                interface_management=interface_management,
                failed_retry=failed_retry,
                connectivity_monitoring=connectivity_monitoring,
                raw_config=config.copy()
            )

            self.logger.info('Configuration loaded successfully',
                           extra={'interface_number': self.interface_number,
                                  'primary_sim': primary_sim_slot,
                                  'connectivity_monitoring_enabled': connectivity_monitoring.get('enabled', True),
                                  'enhanced_reconnection_enabled': enhanced_reconnection.enabled,
                                  'signal_threshold': enhanced_reconnection.signal_threshold})

            return wwan_config

        except Exception as e:
            self.logger.error(f'Failed to load configuration: {e}',
                            extra={'interface_number': self.interface_number})
            raise

    def _parse_enhanced_reconnection_config(self, config: Dict[str, Any]) -> EnhancedReconnectionConfig:
        '''Parse enhanced reconnection strategy configuration'''
        enhanced_value = config.get('enhanced_reconnection', 'enabled')
        if isinstance(enhanced_value, dict):
            enhanced_key = enhanced_value.get('enabled', 'enabled')
            if isinstance(enhanced_key, str):
                enhanced_enabled = enhanced_key.lower() == 'enabled'
            else:
                enhanced_enabled = bool(enhanced_value.get('enabled', True))
        else:
            if isinstance(enhanced_value, str):
                enhanced_enabled = enhanced_value.lower() == 'enabled'
            else:
                enhanced_enabled = bool(enhanced_value)

        return EnhancedReconnectionConfig(
            enabled=enhanced_enabled,
            signal_threshold=int(config.get('reconnection_signal_threshold', -85)),
            max_retries=int(config.get('enhanced_reconnection_max_retries', 3)),
            retry_interval_good_signal=int(config.get('retry_interval_good_signal', 30)),
            retry_interval_poor_signal=int(config.get('retry_interval_poor_signal', 120)),
            max_wait_for_signal=int(config.get('max_wait_for_signal', 120)),
            signal_check_interval=int(config.get('signal_check_interval', 10)),
            normal_monitoring_interval=int(config.get('normal_monitoring_interval', 30)),
            signal_strength_buffer=int(config.get('signal_strength_buffer', 5))
        )

    def _parse_interface_management_config(self, config: Dict[str, Any]) -> InterfaceManagementConfig:
        '''Parse network interface management configuration'''
        interface_mgmt = config.get('interface_management', {})

        return InterfaceManagementConfig(
            enabled=interface_mgmt.get('enabled', True),
            bearer_disconnect_delay=interface_mgmt.get('bearer_disconnect_delay', 15),
            registration_recovery_delay=interface_mgmt.get('registration_recovery_delay', 20),
            registration_flap_count=int(interface_mgmt.get('registration_flap_count', 5)),
            registration_flap_window=int(interface_mgmt.get('registration_flap_window', 360)),
            ip_change_delay=interface_mgmt.get('ip_change_delay', 2),
            ensure_link_up_on_connect=interface_mgmt.get('ensure_link_up_on_connect', True),
            monitor_bearer_state=interface_mgmt.get('monitor_bearer_state', True),
            monitor_ip_changes=interface_mgmt.get('monitor_ip_changes', True),
            interface_up_timeout=interface_mgmt.get('interface_up_timeout', 10)
        )

    def _parse_connectivity_monitoring_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        '''Parse and normalize connectivity monitoring configuration'''
        connectivity_config = config.get('connectivity_monitoring', {})

        if connectivity_config:
            # Apply normalization if the method exists (will be imported from state machine)
            try:
                # This will be handled by the state machine's normalize method
                return connectivity_config
            except Exception as e:
                self.logger.warning(f'Could not normalize connectivity config: {e}',
                                  extra={'interface_number': self.interface_number})
                return connectivity_config

        return {}

    def _parse_failed_retry_config(self, config: Dict[str, Any]) -> FailedRetryConfig:
        '''Parse failed-state periodic retry configuration'''
        failed_retry = config.get('failed_retry', {})

        enabled = failed_retry.get('enabled', True)
        if isinstance(enabled, str):
            enabled = enabled.lower() in ('true', 'enabled', '1')

        intervals = failed_retry.get('intervals', [600, 1800, 3600, 7200])
        if isinstance(intervals, str):
            intervals = [int(x.strip()) for x in intervals.split(',') if x.strip()]

        return FailedRetryConfig(
            enabled=bool(enabled),
            intervals=[int(x) for x in intervals],
            max_interval=int(failed_retry.get('max_interval', 7200)),
            escalation_threshold=int(failed_retry.get('escalation_threshold', 3))
        )

    def validate_configuration(self, config: WWANConfiguration) -> bool:
        '''
        Validate loaded configuration for consistency and required values.

        Args:
            config: Loaded WWAN configuration

        Returns:
            bool: True if configuration is valid
        '''
        try:
            # Validate SIM slot
            if config.primary_sim_slot not in [1, 2]:
                self.logger.error(f'Invalid SIM slot: {config.primary_sim_slot}',
                                extra={'interface_number': self.interface_number})
                return False

            # Validate signal threshold range
            if not (-120 <= config.enhanced_reconnection.signal_threshold <= -50):
                self.logger.warning(f'Signal threshold {config.enhanced_reconnection.signal_threshold} '
                                  f'is outside typical range (-120 to -50 dBm)',
                                  extra={'interface_number': self.interface_number})

            # Validate retry intervals
            if config.enhanced_reconnection.retry_interval_good_signal <= 0:
                self.logger.error('Retry interval for good signal must be positive',
                                extra={'interface_number': self.interface_number})
                return False

            if config.enhanced_reconnection.retry_interval_poor_signal <= 0:
                self.logger.error('Retry interval for poor signal must be positive',
                                extra={'interface_number': self.interface_number})
                return False

            # Validate timeouts
            if config.interface_management.interface_up_timeout <= 0:
                self.logger.error('Interface up timeout must be positive',
                                extra={'interface_number': self.interface_number})
                return False

            self.logger.debug('Configuration validation passed',
                            extra={'interface_number': self.interface_number})
            return True

        except Exception as e:
            self.logger.error(f'Configuration validation failed: {e}',
                            extra={'interface_number': self.interface_number})
            return False
