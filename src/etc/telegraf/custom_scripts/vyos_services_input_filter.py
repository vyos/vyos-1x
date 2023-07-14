#!/usr/bin/env python3
#
# Copyright (C) 2021-2023 VyOS maintainers and contributors
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


import time
from vyos.configquery import ConfigTreeQuery
from vyos.utils.process import is_systemd_service_running
from vyos.utils.process import process_named_running

# Availible services and prouceses
# 1 - service
# 2 - process
services = {
    "protocols bgp"          : "bgpd",
    "protocols ospf"         : "ospfd",
    "protocols ospfv3"       : "ospf6d",
    "protocols rip"          : "ripd",
    "protocols ripng"        : "ripngd",
    "protocols isis"         : "isisd",
    "service pppoe"          : "accel-ppp@pppoe.service",
    "vpn l2tp remote-access" : "accel-ppp@l2tp.service",
    "vpn pptp remote-access" : "accel-ppp@pptp.service",
    "vpn sstp"               : "accel-ppp@sstp.service",
    "vpn ipsec"              : "charon"
}

# Configured services
conf_services = {
    'zebra'   : 0,
    'staticd' : 0,
}
# Get configured service and create list to check if process running
config = ConfigTreeQuery()
for service in services:
    if config.exists(service):
        conf_services[services[service]] = 0

for conf_service in conf_services:
    status = 0
    if ".service" in conf_service:
        # Check systemd service
        if is_systemd_service_running(conf_service):
            status = 1
    else:
        # Check process
        if process_named_running(conf_service):
            status = 1
    print(f'vyos_services,service="{conf_service}" '
          f'status={str(status)}i {str(int(time.time()))}000000000')
