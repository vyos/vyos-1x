#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

import argparse
import logging

import vyos.opmode
import vyos.hostsd_client

from vyos.configquery import ConfigTreeQuery

from vyos.kea import kea_get_active_config
from vyos.kea import kea_get_dhcp_pools
from vyos.kea import kea_get_server_leases

# Configure logging
logger = logging.getLogger(__name__)
# set stream as output
logs_handler = logging.StreamHandler()
logger.addHandler(logs_handler)


def _get_all_server_leases(inet_suffix='4') -> list:
    mappings = []
    try:
        active_config = kea_get_active_config(inet_suffix)
    except Exception:
        raise vyos.opmode.DataUnavailable('Cannot fetch DHCP server configuration')

    try:
        pools = kea_get_dhcp_pools(active_config, inet_suffix)
        mappings = kea_get_server_leases(
            active_config, inet_suffix, pools, state=[], origin=None
        )
    except Exception:
        raise vyos.opmode.DataUnavailable('Cannot fetch DHCP server leases')

    return mappings


if __name__ == '__main__':
    # Parse command arguments
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--inet', action='store_true', help='Use IPv4 DHCP leases')
    group.add_argument('--inet6', action='store_true', help='Use IPv6 DHCP leases')
    args = parser.parse_args()

    inet_suffix = '4' if args.inet else '6'
    service_suffix = '' if args.inet else 'v6'

    if inet_suffix == '6':
        raise vyos.opmode.UnsupportedOperation(
            'Syncing IPv6 DHCP leases are not supported yet'
        )

    # Load configuration
    config = ConfigTreeQuery()

    # Check if DHCP server is configured
    # Using warning instead of error since this check may fail during first-time
    # DHCP server setup when the service is not yet configured in the config tree.
    # This happens when called from systemd's ExecStartPost the first time.
    if not config.exists(f'service dhcp{service_suffix}-server'):
        logger.warning(f'DHCP{service_suffix} server is not configured')

    # Check if hostfile-update is enabled
    if not config.exists(f'service dhcp{service_suffix}-server hostfile-update'):
        logger.debug(
            f'Hostfile update is disabled for DHCP{service_suffix} server, skipping hosts update'
        )
        exit(0)

    lease_data = _get_all_server_leases(inet_suffix)

    try:
        hc = vyos.hostsd_client.Client()

        for mapping in lease_data:
            ip_addr = mapping.get('ip')
            mac_addr = mapping.get('mac')
            name = mapping.get('hostname')
            name = name if name else f'host-{mac_addr.replace(":", "-")}'
            domain = mapping.get('domain')
            fqdn = f'{name}.{domain}' if domain else name
            hc.add_hosts(
                {
                    f'dhcp-server-{ip_addr}': {
                        fqdn: {'address': [ip_addr], 'aliases': []}
                    }
                }
            )

        hc.apply()

        logger.debug('Hosts store updated successfully')

    except vyos.hostsd_client.VyOSHostsdError as e:
        raise vyos.opmode.InternalError(str(e))
