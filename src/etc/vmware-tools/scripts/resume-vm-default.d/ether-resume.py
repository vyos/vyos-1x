#!/usr/bin/env python3
#
# Copyright (C) 2018-2023 VyOS maintainers and contributors
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
import syslog

from vyos import ConfigError
from vyos.config import Config
from vyos.utils.process import run

def get_config():
    c = Config()
    interfaces = dict()
    for intf in c.list_effective_nodes('interfaces ethernet'):
        # skip interfaces that are disabled
        check_disable = f'interfaces ethernet {intf} disable'
        if c.exists_effective(check_disable):
            continue

        # get addresses configured on the interface
        intf_addresses = c.return_effective_values(
            f'interfaces ethernet {intf} address')
        interfaces[intf] = [addr.strip("'") for addr in intf_addresses]
    return interfaces

def apply(config):
    syslog.openlog(ident='ether-resume', logoption=syslog.LOG_PID,
                   facility=syslog.LOG_INFO)

    for intf, addresses in config.items():
        # bring the interface up
        cmd = f'ip link set dev {intf} up'
        syslog.syslog(cmd)
        run(cmd)

        # add configured addresses to interface
        for addr in addresses:
            # dhcp is handled by netplug
            if addr in ['dhcp', 'dhcpv6']:
                continue
            cmd = f'ip address add {addr} dev {intf}'
            syslog.syslog(cmd)
            run(cmd)

if __name__ == '__main__':
    try:
        config = get_config()
        apply(config)
    except ConfigError as e:
        print(e)
        sys.exit(1)
