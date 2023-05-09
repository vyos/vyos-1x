#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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

import logging
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from subprocess import run, TimeoutExpired
from sys import exit

from psutil import net_if_addrs, AF_LINK
from systemd.journal import JournalHandler
from yaml import safe_load

from vyos.template import render

# define a path to the configuration file and template
config_file = '/etc/cloud/cloud.cfg.d/20_vyos_network.cfg'
template_file = 'system/cloud_init_networking.j2'


def check_interface_dhcp(iface_name: str) -> bool:
    """Check DHCP client can work on an interface

    Args:
        iface_name (str): interface name

    Returns:
        bool: check result
    """
    dhclient_command: list[str] = [
        'dhclient', '-4', '-1', '-q', '--no-pid', '-sf', '/bin/true', iface_name
    ]
    check_result = False
    # try to get an IP address
    # we use dhclient behavior here to speedup detection
    # if dhclient receives a configuration and configure an interface
    # it switch to background
    # If no - it will keep running in foreground
    try:
        run(['ip', 'l', 'set', iface_name, 'up'])
        run(dhclient_command, timeout=5)
        check_result = True
    except TimeoutExpired:
        pass
    finally:
        run(['ip', 'l', 'set', iface_name, 'down'])

    logger.info(f'DHCP server was found on {iface_name}: {check_result}')
    return check_result


def dhclient_cleanup() -> None:
    """Clean up after dhclients
    """
    run(['killall', 'dhclient'])
    leases_file: Path = Path('/var/lib/dhcp/dhclient.leases')
    leases_file.unlink(missing_ok=True)
    logger.debug('cleaned up after dhclients')


def dict_interfaces() -> dict[str, str]:
    """Return list of available network interfaces except loopback

    Returns:
        list[str]: a list of interfaces
    """
    interfaces_dict: dict[str, str] = {}
    ifaces = net_if_addrs()
    for iface_name, iface_addresses in ifaces.items():
        # we do not need loopback interface
        if iface_name == 'lo':
            continue
        # check other interfaces for MAC addresses
        for iface_addr in iface_addresses:
            if iface_addr.family == AF_LINK and iface_addr.address:
                interfaces_dict[iface_name] = iface_addr.address
                continue

    logger.debug(f'found interfaces: {interfaces_dict}')
    return interfaces_dict


def need_to_check() -> bool:
    """Check if we need to perform DHCP checks

    Returns:
        bool: check result
    """
    # if cloud-init config does not exist, we do not need to do anything
    ci_config_vyos = Path('/etc/cloud/cloud.cfg.d/20_vyos_custom.cfg')
    if not ci_config_vyos.exists():
        logger.info(
            'No need to check interfaces: Cloud-init config file was not found')
        return False

    # load configuration file
    try:
        config = safe_load(ci_config_vyos.read_text())
    except:
        logger.error('Cloud-init config file has a wrong format')
        return False

    # check if we have in config configured option
    # vyos_config_options:
    #   network_preconfigure: true
    if not config.get('vyos_config_options', {}).get('network_preconfigure'):
        logger.info(
            'No need to check interfaces: Cloud-init config option "network_preconfigure" is not set'
        )
        return False

    return True


if __name__ == '__main__':
    # prepare logger
    logger = logging.getLogger(__name__)
    logger.addHandler(JournalHandler(SYSLOG_IDENTIFIER=Path(__file__).name))
    logger.setLevel(logging.INFO)

    # we need to give udev some time to rename all interfaces
    # this is placed before need_to_check() call, because we are not always
    # need to preconfigure cloud-init, but udev always need to finish its work
    # before cloud-init start
    run(['udevadm', 'settle'])
    logger.info('udev finished its work, we continue')

    # do not perform any checks if this is not required
    if not need_to_check():
        exit()

    # get list of interfaces and check them
    interfaces_dhcp: list[dict[str, str]] = []
    interfaces_dict: dict[str, str] = dict_interfaces()

    with ProcessPoolExecutor(max_workers=len(interfaces_dict)) as executor:
        iface_check_results = [{
            'dhcp': executor.submit(check_interface_dhcp, iface_name),
            'append': {
                'name': iface_name,
                'mac': iface_mac
            }
        } for iface_name, iface_mac in interfaces_dict.items()]

    dhclient_cleanup()

    for iface_check_result in iface_check_results:
        if iface_check_result.get('dhcp').result():
            interfaces_dhcp.append(iface_check_result.get('append'))

    # render cloud-init config
    if interfaces_dhcp:
        logger.debug('rendering cloud-init network configuration')
        render(config_file, template_file, {'ifaces_list': interfaces_dhcp})

    exit()
