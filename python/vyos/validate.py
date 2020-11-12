# Copyright 2018-2020 VyOS maintainers and contributors <maintainers@vyos.io>
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
from vyos.util import cmd

# Important note when you are adding new validation functions:
#
# The Control class will analyse the signature of the function in this file
# and will build the parameters to be passed to it.
#
# The parameter names "ifname" and "self" will get the Interface name and class
# parameters with default will be left unset
# all other paramters will receive the value to check

def is_ip(addr):
    """ Check addr if it is an IPv4 or IPv6 address """
    return is_ipv4(addr) or is_ipv6(addr)

def is_ipv4(addr):
    from vyos.template import vyos_ipv4
    return vyos_ipv4(addr)

def is_ipv6(addr):
    from vyos.template import vyos_ipv6
    return vyos_ipv6(addr)

def is_ipv6_link_local(addr):
    """ Check if addrsss is an IPv6 link-local address. Returns True/False """
    from ipaddress import IPv6Address
    addr = addr.split('%')[0]
    if is_ipv6(addr):
        if IPv6Address(addr).is_link_local:
            return True

    return False

def _are_same_ip(one, two):
    from socket import AF_INET
    from socket import AF_INET6
    from socket import inet_pton
    # compare the binary representation of the IP
    f_one = AF_INET if is_ipv4(one) else AF_INET6
    s_two = AF_INET if is_ipv4(two) else AF_INET6
    return inet_pton(f_one, one) == inet_pton(f_one, two)

def is_intf_addr_assigned(intf, addr):
    if '/' in addr:
        ip,mask = addr.split('/')
        return _is_intf_addr_assigned(intf, ip, mask)
    return _is_intf_addr_assigned(intf, addr)

def _is_intf_addr_assigned(intf, address, netmask=''):
    """
    Verify if the given IPv4/IPv6 address is assigned to specific interface.
    It can check both a single IP address (e.g. 192.0.2.1 or a assigned CIDR
    address 192.0.2.1/24.
    """

    # check if the requested address type is configured at all
    # {
    # 17: [{'addr': '08:00:27:d9:5b:04', 'broadcast': 'ff:ff:ff:ff:ff:ff'}],
    # 2:  [{'addr': '10.0.2.15', 'netmask': '255.255.255.0', 'broadcast': '10.0.2.255'}],
    # 10: [{'addr': 'fe80::a00:27ff:fed9:5b04%eth0', 'netmask': 'ffff:ffff:ffff:ffff::'}]
    # }
    try:
        ifaces = netifaces.ifaddresses(intf)
    except ValueError as e:
        print(e)
        return False

    # determine IP version (AF_INET or AF_INET6) depending on passed address
    addr_type = netifaces.AF_INET if is_ipv4(address) else netifaces.AF_INET6

    # Check every IP address on this interface for a match
    for ip in ifaces.get(addr_type,[]):
        # ip can have the interface name in the 'addr' field, we need to remove it
        # {'addr': 'fe80::a00:27ff:fec5:f821%eth2', 'netmask': 'ffff:ffff:ffff:ffff::'}
        ip_addr = ip['addr'].split('%')[0]

        if not _are_same_ip(address, ip_addr):
            continue

        # we do not have a netmask to compare against, they are the same
        if netmask == '':
            return True

        prefixlen = ''
        if is_ipv4(ip_addr):
            prefixlen = sum([bin(int(_)).count('1') for _ in ip['netmask'].split('.')])
        else:
            prefixlen = sum([bin(int(_,16)).count('1') for _ in ip['netmask'].split(':') if _])

        if str(prefixlen) == netmask:
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
    """ Check if supplied IPv4/IPv6 address is a loopback address """
    from ipaddress import ip_address
    return ip_address(addr).is_loopback

def is_subnet_connected(subnet, primary=False):
    """
    Verify is the given IPv4/IPv6 subnet is connected to any interface on this
    system.

    primary check if the subnet is reachable via the primary IP address of this
    interface, or in other words has a broadcast address configured. ISC DHCP
    for instance will complain if it should listen on non broadcast interfaces.

    Return True/False
    """
    from ipaddress import ip_address
    from ipaddress import ip_network

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
            if ip_address(ip) in ip_network(subnet):
                return True
        else:
            # Check every assigned IP address if it is connected to the subnet
            # in question
            for ip in netifaces.ifaddresses(interface)[addr_type]:
                # remove interface extension (e.g. %eth0) that gets thrown on the end of _some_ addrs
                addr = ip['addr'].split('%')[0]
                if ip_address(addr) in ip_network(subnet):
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
    if not str(n).isnumeric():
        raise ValueError(f'{n} must be a number')


def assert_positive(n, smaller=0):
    assert_number(n)
    if int(n) < smaller:
        raise ValueError(f'{n} is smaller than {smaller}')


def assert_mtu(mtu, ifname):
    assert_number(mtu)

    import json
    out = cmd(f'ip -j -d link show dev {ifname}')
    # [{"ifindex":2,"ifname":"eth0","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":1500,"qdisc":"pfifo_fast","operstate":"UP","linkmode":"DEFAULT","group":"default","txqlen":1000,"link_type":"ether","address":"08:00:27:d9:5b:04","broadcast":"ff:ff:ff:ff:ff:ff","promiscuity":0,"min_mtu":46,"max_mtu":16110,"inet6_addr_gen_mode":"none","num_tx_queues":1,"num_rx_queues":1,"gso_max_size":65536,"gso_max_segs":65535}]
    parsed = json.loads(out)[0]
    min_mtu = int(parsed.get('min_mtu', '0'))
    # cur_mtu = parsed.get('mtu',0),
    max_mtu = int(parsed.get('max_mtu', '0'))
    cur_mtu = int(mtu)

    if (min_mtu and cur_mtu < min_mtu) or cur_mtu < 68:
        raise ValueError(f'MTU is too small for interface "{ifname}": {mtu} < {min_mtu}')
    if (max_mtu and cur_mtu > max_mtu) or cur_mtu > 65536:
        raise ValueError(f'MTU is too small for interface "{ifname}": {mtu} > {max_mtu}')


def assert_mac(m):
    split = m.split(':')
    size = len(split)

    # a mac address consits out of 6 octets
    if size != 6:
        raise ValueError(f'wrong number of MAC octets ({size}): {m}')

    octets = []
    try:
        for octet in split:
            octets.append(int(octet, 16))
    except ValueError:
        raise ValueError(f'invalid hex number "{octet}" in : {m}')

    # validate against the first mac address byte if it's a multicast
    # address
    if octets[0] & 1:
        raise ValueError(f'{m} is a multicast MAC address')

    # overall mac address is not allowed to be 00:00:00:00:00:00
    if sum(octets) == 0:
        raise ValueError('00:00:00:00:00:00 is not a valid MAC address')

    if octets[:5] == (0, 0, 94, 0, 1):
        raise ValueError(f'{m} is a VRRP MAC address')

def has_address_configured(conf, intf):
    """
    Checks if interface has an address configured.
    Checks the following config nodes:
    'address', 'ipv6 address eui64', 'ipv6 address autoconf'

    Returns True if interface has address configured, False if it doesn't.
    """
    from vyos.ifconfig import Section
    ret = False

    old_level = conf.get_level()
    conf.set_level([])

    intfpath = 'interfaces ' + Section.get_config_path(intf)
    if ( conf.exists(f'{intfpath} address') or
            conf.exists(f'{intfpath} ipv6 address autoconf') or
            conf.exists(f'{intfpath} ipv6 address eui64') ):
        ret = True

    conf.set_level(old_level)
    return ret
