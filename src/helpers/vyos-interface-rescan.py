#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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
#
#

import os
import stat
import argparse
import logging
import netaddr

from vyos.configtree import ConfigTree
from vyos.defaults import directories
from vyos.utils.permission import get_cfg_group_id

debug = False

vyos_udev_dir = directories['vyos_udev_dir']
vyos_log_dir = directories['log']
log_file = os.path.splitext(os.path.basename(__file__))[0]
vyos_log_file = os.path.join(vyos_log_dir, log_file)

logger = logging.getLogger(__name__)
handler = logging.FileHandler(vyos_log_file, mode='a')
formatter = logging.Formatter('%(levelname)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

passlist = {
    '02:07:01' : 'Interlan',
    '02:60:60' : '3Com',
    '02:60:8c' : '3Com',
    '02:a0:c9' : 'Intel',
    '02:aa:3c' : 'Olivetti',
    '02:cf:1f' : 'CMC',
    '02:e0:3b' : 'Prominet',
    '02:e6:d3' : 'BTI',
    '52:54:00' : 'Realtek',
    '52:54:4c' : 'Novell 2000',
    '52:54:ab' : 'Realtec',
    'e2:0c:0f' : 'Kingston Technologies'
}

def is_multicast(addr: netaddr.eui.EUI) -> bool:
    return bool(addr.words[0] & 0b1)

def is_locally_administered(addr: netaddr.eui.EUI) -> bool:
    return bool(addr.words[0] & 0b10)

def is_on_passlist(hwid: str) -> bool:
    top = hwid.rsplit(':', 3)[0]
    if top in list(passlist):
        return True
    return False

def is_persistent(hwid: str) -> bool:
    addr = netaddr.EUI(hwid)
    if is_multicast(addr):
        return False
    if is_locally_administered(addr) and not is_on_passlist(hwid):
        return False
    return True

def get_wireless_physical_device(intf: str) -> str:
    if 'wlan' not in intf:
        return ''
    try:
        tmp = os.readlink(f'/sys/class/net/{intf}/phy80211')
    except OSError:
        logger.critical(f"Failed to read '/sys/class/net/{intf}/phy80211'")
        return ''
    phy = os.path.basename(tmp)
    logger.info(f"wireless phy is {phy}")
    return phy

def get_interface_type(intf: str) -> str:
    if 'eth' in intf:
        intf_type = 'ethernet'
    elif 'wlan' in intf:
        intf_type = 'wireless'
    else:
        logger.critical('Unrecognized interface type!')
        intf_type = ''
    return intf_type

def get_new_interfaces() -> dict:
    """ Read any new interface data left in /run/udev/vyos by vyos_net_name
    """
    interfaces = {}

    for intf in os.listdir(vyos_udev_dir):
        path = os.path.join(vyos_udev_dir, intf)
        try:
            with open(path) as f:
                hwid = f.read().rstrip()
        except OSError as e:
            logger.error(f"OSError {e}")
            continue
        interfaces[intf] = hwid

    # reverse sort to simplify insertion in config
    interfaces = {key: value for key, value in sorted(interfaces.items(),
                                                      reverse=True)}
    return interfaces

def filter_interfaces(intfs: dict) -> dict:
    """ Ignore no longer existing interfaces or non-persistent mac addresses
    """
    filtered = {}

    for intf, hwid in intfs.items():
        if not os.path.isdir(os.path.join('/sys/class/net', intf)):
            continue
        if not is_persistent(hwid):
            continue
        filtered[intf] = hwid

    return filtered

def interface_rescan(config_path: str):
    """ Read new data and update config file
    """
    interfaces = get_new_interfaces()

    logger.debug(f"interfaces from udev: {interfaces}")

    interfaces = filter_interfaces(interfaces)

    logger.debug(f"filtered interfaces: {interfaces}")

    try:
        with open(config_path) as f:
            config_file = f.read()
    except OSError as e:
        logger.critical(f"OSError {e}")
        exit(1)

    config = ConfigTree(config_file)

    for intf, hwid in interfaces.items():
        logger.info(f"Writing '{intf}' '{hwid}' to config file")
        intf_type = get_interface_type(intf)
        if not intf_type:
            continue
        if not config.exists(['interfaces', intf_type]):
            config.set(['interfaces', intf_type])
            config.set_tag(['interfaces', intf_type])
        config.set(['interfaces', intf_type, intf, 'hw-id'], value=hwid)

        if intf_type == 'wireless':
            phy = get_wireless_physical_device(intf)
            if not phy:
                continue
            config.set(['interfaces', intf_type, intf, 'physical-device'],
                       value=phy)

    try:
        with open(config_path, 'w') as f:
            f.write(config.to_string())
    except OSError as e:
        logger.critical(f"OSError {e}")

def main():
    global debug

    argparser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter)
    argparser.add_argument('configfile', type=str)
    argparser.add_argument('--debug', action='store_true')
    args = argparser.parse_args()

    if args.debug:
        debug = True
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    configfile = args.configfile

    # preserve vyattacfg group write access to running config
    os.setgid(get_cfg_group_id())
    os.umask(0o002)

    # log file perms are not automatic; this could be cleaner by moving to a
    # logging config file
    os.chown(vyos_log_file, 0, get_cfg_group_id())
    os.chmod(vyos_log_file,
             stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH)

    interface_rescan(configfile)

if __name__ == '__main__':
    main()
