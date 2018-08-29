# Copyright 2018 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import netifaces
import ipaddress

def is_ipv4(addr):
    """
    Check addr if it is an IPv4 address/network.

    Return True/False
    """
    if ipaddress.ip_network(addr).version == 4:
        return True
    else:
        return False

def is_ipv6(addr):
    """
    Check addr if it is an IPv6 address/network.

    Return True/False
    """
    if ipaddress.ip_network(addr).version == 6:
        return True
    else:
        return False

def is_addr_assigned(addr):
    """
    Verify if the given IPv4/IPv6 address is assigned to any interface on this system

    Return True/False
    """

    # determine IP version (AF_INET or AF_INET6) depending on passed address
    addr_type = netifaces.AF_INET
    if is_ipv6(addr):
        addr_type = netifaces.AF_INET6

    for interface in netifaces.interfaces():
        # check if the requested address type is configured at all
        if addr_type in netifaces.ifaddresses(interface).keys():
            # Check every IP address on this interface for a match
            for ip in netifaces.ifaddresses(interface)[addr_type]:
                # Check if it matches to the address requested
                if ip['addr'] == addr:
                    return True

    return False

