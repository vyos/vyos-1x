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
#
# Make discovered interfaces visible in the configuration, so a newly
# installed NIC shows up without the operator adding it by hand.
#
# T3871: the node is created bare. Writing a 'hw-id' back into config.boot is
# what used to make a bad guess unrecoverable - naming belongs to the store.

import argparse
import logging
import os
import stat
from pathlib import Path

from vyos.configtree import ConfigTree
from vyos.defaults import directories
from vyos.ifconfig.ifname_store import load_store
from vyos.utils.permission import get_cfg_group_id

debug = False

vyos_log_dir = directories['log']
log_file = os.path.splitext(os.path.basename(__file__))[0]
vyos_log_file = os.path.join(vyos_log_dir, log_file)

logger = logging.getLogger(__name__)
handler = logging.FileHandler(vyos_log_file, mode='a')
formatter = logging.Formatter('%(levelname)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def get_interface_type(intf: str) -> str:
    if intf.startswith('eth'):
        return 'ethernet'
    if intf.startswith('wlan'):
        return 'wireless'
    logger.critical(f"Unrecognized interface type for '{intf}'")
    return ''


def get_wireless_physical_device(intf: str) -> str:
    """The phy a wireless interface belongs to."""
    try:
        return os.path.basename(
            os.readlink(f'/sys/class/net/{intf}/phy80211'))
    except OSError:
        return ''


def interface_rescan(config_path: str):
    """Add a node for every named interface which does not have one yet."""
    store = load_store()

    # a reserved name whose hardware is absent has nothing to create a node for
    names = [name for name in sorted(store.get('interfaces', {}))
             if Path(f'/sys/class/net/{name}').is_dir()]

    logger.debug(f'named interfaces present: {names}')

    try:
        config_file = Path(config_path).read_text()
    except OSError as e:
        logger.critical(f'OSError {e}')
        exit(1)

    config = ConfigTree(config_file)
    changed = False

    for intf in names:
        intf_type = get_interface_type(intf)
        if not intf_type:
            continue
        if config.exists(['interfaces', intf_type, intf]):
            continue

        logger.info(f"Adding '{intf}' to the configuration")
        if not config.exists(['interfaces', intf_type]):
            config.set(['interfaces', intf_type])
            config.set_tag(['interfaces', intf_type])
        config.set(['interfaces', intf_type, intf])
        changed = True

        if intf_type == 'wireless':
            phy = get_wireless_physical_device(intf)
            if phy:
                config.set(['interfaces', intf_type, intf, 'physical-device'],
                           value=phy)

    if not changed:
        return

    try:
        Path(config_path).write_text(config.to_string())
    except OSError as e:
        logger.critical(f'OSError {e}')
        exit(1)


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
