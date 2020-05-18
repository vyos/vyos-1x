#!/usr/bin/env python3
#
# Copyright (C) 2018-2020 VyOS maintainers and contributors
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

import sys
import syslog as sl

from vyos.config import Config
from vyos import ConfigError
from vyos.command import run


def get_config():
    c = Config()
    interfaces = dict()
    for intf in c.list_effective_nodes('interfaces ethernet'):
        # skip interfaces that are disabled or is configured for dhcp
        check_disable = "interfaces ethernet {} disable".format(intf)
        check_dhcp = "interfaces ethernet {} address dhcp".format(intf)
        if c.exists_effective(check_disable):
            continue

        # get addresses configured on the interface
        intf_addresses = c.return_effective_values(
            "interfaces ethernet {} address".format(intf)
        )
        interfaces[intf] = [addr.strip("'") for addr in intf_addresses]
    return interfaces


def apply(config):
    for intf, addresses in config.items():
        # bring the interface up
        cmd = ["ip", "link", "set", "dev", intf, "up"]
        sl.syslog(sl.LOG_NOTICE, " ".join(cmd))
        run(cmd)

        # add configured addresses to interface
        for addr in addresses:
            if addr == "dhcp":
                cmd = ["dhclient", intf]
            else:
                cmd = ["ip", "address", "add", addr, "dev", intf]
            sl.syslog(sl.LOG_NOTICE, " ".join(cmd))
            run(cmd)


if __name__ == '__main__':
    try:
        config = get_config()
        apply(config)
    except ConfigError as e:
        print(e)
        sys.exit(1)
