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

def is_ip(addr):
    """
    Check addr if it is an IPv4 or IPv6 address
    """
    return is_ipv4(addr) or is_ipv6(addr)

def is_ipv4(addr):
    """
    Check addr if it is an IPv4 address/network. Returns True/False
    """

    # With the below statement we can check for IPv4 networks and host
    # addresses at the same time
    try:
        if ipaddress.ip_address(addr.split(r'/')[0]).version == 4:
            return True
    except:
        pass

    return False

def is_ipv6(addr):
    """
    Check addr if it is an IPv6 address/network. Returns True/False
    """

    # With the below statement we can check for IPv4 networks and host
    # addresses at the same time
    try:
        if ipaddress.ip_network(addr.split(r'/')[0]).version == 6:
            return True
    except:
        pass

    return False

def is_ipv6_link_local(addr):
    """
    Check addr if it is an IPv6 link-local address/network. Returns True/False
    """

    addr = addr.split('%')[0]
    if is_ipv6(addr):
        if ipaddress.IPv6Address(addr).is_link_local:
            return True

    return False

def is_intf_addr_assigned(intf, addr):
    """
    Verify if the given IPv4/IPv6 address is assigned to specific interface.
    It can check both a single IP address (e.g. 192.0.2.1 or a assigned CIDR
    address 192.0.2.1/24.
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
            # If passed address contains a '/' indicating a normalized IP
            # address we have to take this into account, too
            if r'/' in addr:
                prefixlen = ''
                if is_ipv6(addr):
                     # Note that currently expanded netmasks are not supported. That means
                     # 2001:db00::0/24 is a valid argument while 2001:db00::0/ffff:ff00:: not.
                     # see https://docs.python.org/3/library/ipaddress.html
                     bits =  bin( int(ip['netmask'].replace(':',''), 16) ).count('1')
                     prefixlen = '/' + str(bits)

                else:
                     prefixlen = '/' + str(ipaddress.IPv4Network('0.0.0.0/' + ip['netmask']).prefixlen)

                # construct temporary variable holding IPv6 address and netmask
                # in CIDR notation
                tmp = ip['addr'] + prefixlen
                if addr == tmp:
                    return True

            elif ip['addr'] == addr:
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

def is_loopback_addr(addr):
    """
    Check if supplied IPv4/IPv6 address is a loopback address
    """
    return ipaddress.ip_address(addr).is_loopback

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


def assert_boolean(b):
    if int(b) not in (0, 1):
        raise ValueError(f'Value {b} out of range')


def assert_range(value, lower=0, count=3):
    if int(value) not in range(lower,lower+count):
        raise ValueError("Value out of range")


def assert_list(s, l):
    if s not in l:
        o = ' or '.join([f'"{n}"' for n in l])
        raise ValueError(f'state must be {o}, got {s}')


def assert_number(n):
    if not n.isnumeric():
        raise ValueError(f'{n} must be a number')


def assert_positive(n, smaller=0):
    assert_number(n)
    if int(n) < smaller:
        raise ValueError(f'{n} is smaller than {limit}')


def assert_mtu(mtu, min=68, max=9000):
    assert_number(mtu)
    if int(mtu) < min or int(mtu) > max:
        raise ValueError(f'Invalid MTU size: "{mtu}"')


def assert_mac(m):
    octets = [int(i, 16) for i in m.split(':')]

    # a mac address consits out of 6 octets
    if len(octets) != 6:
        raise ValueError(f'wrong number of MAC octets: {octets}')

    # validate against the first mac address byte if it's a multicast
    # address
    if octets[0] & 1:
        raise ValueError(f'{m} is a multicast MAC address')

    # overall mac address is not allowed to be 00:00:00:00:00:00
    if sum(octets) == 0:
        raise ValueError('00:00:00:00:00:00 is not a valid MAC address')

    if octets[:5] == (0, 0, 94, 0, 1):
        raise ValueError(f'{m} is a VRRP MAC address')
