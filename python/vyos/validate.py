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
    Check addr if it is an IPv4 address/network. Returns True/False
    """

    # With the below statement we can check for IPv4 networks and host
    # addresses at the same time
    if ipaddress.ip_address(addr.split(r'/')[0]).version == 4:
        return True
    else:
        return False

def is_ipv6(addr):
    """
    Check addr if it is an IPv6 address/network. Returns True/False
    """

    # With the below statement we can check for IPv4 networks and host
    # addresses at the same time
    if ipaddress.ip_network(addr.split(r'/')[0]).version == 6:
        return True
    else:
        return False

def is_intf_addr_assigned(intf, addr):
    """
    Verify if the given IPv4/IPv6 address is assigned to specific interface
    """

    # determine IP version (AF_INET or AF_INET6) depending on passed address
    addr_type = netifaces.AF_INET
    if is_ipv6(addr):
        addr_type = netifaces.AF_INET6

    # check if the requested address type is configured at all
    try:
        netifaces.ifaddresses(intf)
    except ValueError as e:
        print(e)
        return False

    if addr_type in netifaces.ifaddresses(intf).keys():
        # Check every IP address on this interface for a match
        for ip in netifaces.ifaddresses(intf)[addr_type]:
            # Check if it matches to the address requested
            if ip['addr'] == addr:
                return True

    return False

def is_addr_assigned(addr):
    """
    Verify if the given IPv4/IPv6 address is assigned to any interface
    """

    for intf in netifaces.interfaces():
        tmp = is_intf_addr_assigned(intf, addr)
        if tmp == True:
            return True

    return False

def is_subnet_connected(subnet, primary=False):
    """
    Verify is the given IPv4/IPv6 subnet is connected to any interface on this
    system.

    primary check if the subnet is reachable via the primary IP address of this
    interface, or in other words has a broadcast address configured. ISC DHCP
    for instance will complain if it should listen on non broadcast interfaces.

    Return True/False
    """

    # determine IP version (AF_INET or AF_INET6) depending on passed address
    addr_type = netifaces.AF_INET
    if is_ipv6(subnet):
        addr_type = netifaces.AF_INET6

    for interface in netifaces.interfaces():
        # check if the requested address type is configured at all
        if addr_type not in netifaces.ifaddresses(interface).keys():
            continue

        # An interface can have multiple addresses, but some software components
        # only support the primary address :(
        if primary:
            ip = netifaces.ifaddresses(interface)[addr_type][0]['addr']
            if ipaddress.ip_address(ip) in ipaddress.ip_network(subnet):
                return True
        else:
            # Check every assigned IP address if it is connected to the subnet
            # in question
            for ip in netifaces.ifaddresses(interface)[addr_type]:
                # remove interface extension (e.g. %eth0) that gets thrown on the end of _some_ addrs
                addr = ip['addr'].split('%')[0]
                if ipaddress.ip_address(addr) in ipaddress.ip_network(subnet):
                    return True

    return False
