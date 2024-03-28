# Copyright 2023 VyOS maintainers and contributors <maintainers@vyos.io>
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

def _are_same_ip(one, two):
    from socket import AF_INET
    from socket import AF_INET6
    from socket import inet_pton
    from vyos.template import is_ipv4
    # compare the binary representation of the IP
    f_one = AF_INET if is_ipv4(one) else AF_INET6
    s_two = AF_INET if is_ipv4(two) else AF_INET6
    return inet_pton(f_one, one) == inet_pton(f_one, two)

def get_protocol_by_name(protocol_name):
    """Get protocol number by protocol name

       % get_protocol_by_name('tcp')
       % 6
    """
    import socket
    try:
        protocol_number = socket.getprotobyname(protocol_name)
        return protocol_number
    except socket.error:
        return protocol_name

def interface_exists(interface) -> bool:
    import os
    return os.path.exists(f'/sys/class/net/{interface}')

def is_netns_interface(interface, netns):
    from vyos.utils.process import rc_cmd
    rc, out = rc_cmd(f'sudo ip netns exec {netns} ip link show dev {interface}')
    if rc == 0:
        return True
    return False

def get_netns_all() -> list:
    from json import loads
    from vyos.utils.process import cmd
    tmp = loads(cmd('ip --json netns ls'))
    return [ netns['name'] for netns in tmp ]

def get_vrf_members(vrf: str) -> list:
    """
    Get list of interface VRF members
    :param vrf: str
    :return: list
    """
    import json
    from vyos.utils.process import cmd
    interfaces = []
    try:
        if not interface_exists(vrf):
            raise ValueError(f'VRF "{vrf}" does not exist!')
        output = cmd(f'ip --json --brief link show vrf {vrf}')
        answer = json.loads(output)
        for data in answer:
            if 'ifname' in data:
                interfaces.append(data.get('ifname'))
    except:
        pass
    return interfaces

def get_interface_vrf(interface):
    """ Returns VRF of given interface """
    from vyos.utils.dict import dict_search
    from vyos.utils.network import get_interface_config
    tmp = get_interface_config(interface)
    if dict_search('linkinfo.info_slave_kind', tmp) == 'vrf':
        return tmp['master']
    return 'default'

def get_interface_config(interface):
    """ Returns the used encapsulation protocol for given interface.
        If interface does not exist, None is returned.
    """
    if not interface_exists(interface):
        return None
    from json import loads
    from vyos.utils.process import cmd
    tmp = loads(cmd(f'ip --detail --json link show dev {interface}'))[0]
    return tmp

def get_interface_address(interface):
    """ Returns the used encapsulation protocol for given interface.
        If interface does not exist, None is returned.
    """
    if not interface_exists(interface):
        return None
    from json import loads
    from vyos.utils.process import cmd
    tmp = loads(cmd(f'ip --detail --json addr show dev {interface}'))[0]
    return tmp

def get_interface_namespace(interface: str):
    """
       Returns wich netns the interface belongs to
    """
    from json import loads
    from vyos.utils.process import cmd

    # Bail out early if netns does not exist
    tmp = cmd(f'ip --json netns ls')
    if not tmp: return None

    for ns in loads(tmp):
        netns = f'{ns["name"]}'
        # Search interface in each netns
        data = loads(cmd(f'ip netns exec {netns} ip --json link show'))
        for tmp in data:
            if interface == tmp["ifname"]:
                return netns

def is_ipv6_tentative(iface: str, ipv6_address: str) -> bool:
    """Check if IPv6 address is in tentative state.

    This function checks if an IPv6 address on a specific network interface is
    in the tentative state. IPv6 tentative addresses are not fully configured
    and are undergoing Duplicate Address Detection (DAD) to ensure they are
    unique on the network.

    Args:
        iface (str): The name of the network interface.
        ipv6_address (str): The IPv6 address to check.

    Returns:
        bool: True if the IPv6 address is tentative, False otherwise.
    """
    import json
    from vyos.utils.process import rc_cmd

    rc, out = rc_cmd(f'ip -6 --json address show dev {iface}')
    if rc:
        return False

    data = json.loads(out)
    for addr_info in data[0]['addr_info']:
        if (
            addr_info.get('local') == ipv6_address and
            addr_info.get('tentative', False)
        ):
            return True
    return False

def is_wwan_connected(interface):
    """ Determine if a given WWAN interface, e.g. wwan0 is connected to the
    carrier network or not """
    import json
    from vyos.utils.dict import dict_search
    from vyos.utils.process import cmd
    from vyos.utils.process import is_systemd_service_active

    if not interface.startswith('wwan'):
        raise ValueError(f'Specified interface "{interface}" is not a WWAN interface')

    # ModemManager is required for connection(s) - if service is not running,
    # there won't be any connection at all!
    if not is_systemd_service_active('ModemManager.service'):
        return False

    modem = interface.lstrip('wwan')

    tmp = cmd(f'mmcli --modem {modem} --output-json')
    tmp = json.loads(tmp)

    # return True/False if interface is in connected state
    return dict_search('modem.generic.state', tmp) == 'connected'

def get_bridge_fdb(interface):
    """ Returns the forwarding database entries for a given interface """
    if not interface_exists(interface):
        return None
    from json import loads
    from vyos.utils.process import cmd
    tmp = loads(cmd(f'bridge -j fdb show dev {interface}'))
    return tmp

def get_all_vrfs():
    """ Return a dictionary of all system wide known VRF instances """
    from json import loads
    from vyos.utils.process import cmd
    tmp = loads(cmd('ip --json vrf list'))
    # Result is of type [{"name":"red","table":1000},{"name":"blue","table":2000}]
    # so we will re-arrange it to a more nicer representation:
    # {'red': {'table': 1000}, 'blue': {'table': 2000}}
    data = {}
    for entry in tmp:
        name = entry.pop('name')
        data[name] = entry
    return data

def interface_list() -> list:
    from vyos.ifconfig import Section
    """
    Get list of interfaces in system
    :rtype: list
    """
    return Section.interfaces()


def vrf_list() -> list:
    """
    Get list of VRFs in system
    :rtype: list
    """
    return list(get_all_vrfs().keys())

def mac2eui64(mac, prefix=None):
    """
    Convert a MAC address to a EUI64 address or, with prefix provided, a full
    IPv6 address.
    Thankfully copied from https://gist.github.com/wido/f5e32576bb57b5cc6f934e177a37a0d3
    """
    import re
    from ipaddress import ip_network
    # http://tools.ietf.org/html/rfc4291#section-2.5.1
    eui64 = re.sub(r'[.:-]', '', mac).lower()
    eui64 = eui64[0:6] + 'fffe' + eui64[6:]
    eui64 = hex(int(eui64[0:2], 16) ^ 2)[2:].zfill(2) + eui64[2:]

    if prefix is None:
        return ':'.join(re.findall(r'.{4}', eui64))
    else:
        try:
            net = ip_network(prefix, strict=False)
            euil = int('0x{0}'.format(eui64), 16)
            return str(net[euil])
        except:  # pylint: disable=bare-except
            return

def check_port_availability(ipaddress, port, protocol):
    """
    Check if port is available and not used by any service
    Return False if a port is busy or IP address does not exists
    Should be used carefully for services that can start listening
    dynamically, because IP address may be dynamic too
    """
    from socketserver import TCPServer, UDPServer
    from ipaddress import ip_address

    # verify arguments
    try:
        ipaddress = ip_address(ipaddress).compressed
    except:
        raise ValueError(f'The {ipaddress} is not a valid IPv4 or IPv6 address')
    if port not in range(1, 65536):
        raise ValueError(f'The port number {port} is not in the 1-65535 range')
    if protocol not in ['tcp', 'udp']:
        raise ValueError(f'The protocol {protocol} is not supported. Only tcp and udp are allowed')

    # check port availability
    try:
        if protocol == 'tcp':
            server = TCPServer((ipaddress, port), None, bind_and_activate=True)
        if protocol == 'udp':
            server = UDPServer((ipaddress, port), None, bind_and_activate=True)
        server.server_close()
    except Exception as e:
        # errno.h:
        #define EADDRINUSE  98  /* Address already in use */
        if e.errno == 98:
            return False

    return True

def is_listen_port_bind_service(port: int, service: str) -> bool:
    """Check if listen port bound to expected program name
    :param port: Bind port
    :param service: Program name
    :return: bool

    Example:
        % is_listen_port_bind_service(443, 'nginx')
        True
        % is_listen_port_bind_service(443, 'ocserv-main')
        False
    """
    from psutil import net_connections as connections
    from psutil import Process as process
    for connection in connections():
        addr = connection.laddr
        pid = connection.pid
        pid_name = process(pid).name()
        pid_port = addr.port
        if service == pid_name and port == pid_port:
            return True
    return False

def is_ipv6_link_local(addr):
    """ Check if addrsss is an IPv6 link-local address. Returns True/False """
    from ipaddress import ip_interface
    from vyos.template import is_ipv6
    addr = addr.split('%')[0]
    if is_ipv6(addr):
        if ip_interface(addr).is_link_local:
            return True

    return False

def is_addr_assigned(ip_address, vrf=None, return_ifname=False, include_vrf=False) -> bool | str:
    """ Verify if the given IPv4/IPv6 address is assigned to any interface """
    from netifaces import interfaces
    from vyos.utils.network import get_interface_config
    from vyos.utils.dict import dict_search

    for interface in interfaces():
        # Check if interface belongs to the requested VRF, if this is not the
        # case there is no need to proceed with this data set - continue loop
        # with next element
        tmp = get_interface_config(interface)
        if dict_search('master', tmp) != vrf and not include_vrf:
            continue

        if is_intf_addr_assigned(interface, ip_address):
            return interface if return_ifname else True

    return False

def is_intf_addr_assigned(ifname: str, addr: str, netns: str=None) -> bool:
    """
    Verify if the given IPv4/IPv6 address is assigned to specific interface.
    It can check both a single IP address (e.g. 192.0.2.1 or a assigned CIDR
    address 192.0.2.1/24.
    """
    import json
    import jmespath

    from vyos.utils.process import rc_cmd
    from ipaddress import ip_interface

    netns_cmd = f'ip netns exec {netns}' if netns else ''
    rc, out = rc_cmd(f'{netns_cmd} ip --json address show dev {ifname}')
    if rc == 0:
        json_out = json.loads(out)
        addresses = jmespath.search("[].addr_info[].{family: family, address: local, prefixlen: prefixlen}", json_out)
        for address_info in addresses:
            family = address_info['family']
            address = address_info['address']
            prefixlen = address_info['prefixlen']
            # Remove the interface name if present in the given address
            if '%' in addr:
                addr = addr.split('%')[0]
            interface = ip_interface(f"{address}/{prefixlen}")
            if ip_interface(addr) == interface or address == addr:
                return True

    return False

def is_loopback_addr(addr):
    """ Check if supplied IPv4/IPv6 address is a loopback address """
    from ipaddress import ip_address
    return ip_address(addr).is_loopback

def is_wireguard_key_pair(private_key: str, public_key:str) -> bool:
    """
     Checks if public/private keys are keypair
    :param private_key: Wireguard private key
    :type private_key: str
    :param public_key: Wireguard public key
    :type public_key: str
    :return: If public/private keys are keypair returns True else False
    :rtype: bool
    """
    from vyos.utils.process import cmd
    gen_public_key = cmd('wg pubkey', input=private_key)
    if gen_public_key == public_key:
        return True
    else:
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
    from ipaddress import ip_address
    from ipaddress import ip_network

    from netifaces import ifaddresses
    from netifaces import interfaces
    from netifaces import AF_INET
    from netifaces import AF_INET6

    from vyos.template import is_ipv6

    # determine IP version (AF_INET or AF_INET6) depending on passed address
    addr_type = AF_INET
    if is_ipv6(subnet):
        addr_type = AF_INET6

    for interface in interfaces():
        # check if the requested address type is configured at all
        if addr_type not in ifaddresses(interface).keys():
            continue

        # An interface can have multiple addresses, but some software components
        # only support the primary address :(
        if primary:
            ip = ifaddresses(interface)[addr_type][0]['addr']
            if ip_address(ip) in ip_network(subnet):
                return True
        else:
            # Check every assigned IP address if it is connected to the subnet
            # in question
            for ip in ifaddresses(interface)[addr_type]:
                # remove interface extension (e.g. %eth0) that gets thrown on the end of _some_ addrs
                addr = ip['addr'].split('%')[0]
                if ip_address(addr) in ip_network(subnet):
                    return True

    return False

def is_afi_configured(interface: str, afi):
    """ Check if given address family is configured, or in other words - an IP
    address is assigned to the interface. """
    from netifaces import ifaddresses
    from netifaces import AF_INET
    from netifaces import AF_INET6

    if afi not in [AF_INET, AF_INET6]:
        raise ValueError('Address family must be in [AF_INET, AF_INET6]')

    try:
        addresses = ifaddresses(interface)
    except ValueError as e:
        print(e)
        return False

    return afi in addresses

def get_vxlan_vlan_tunnels(interface: str) -> list:
    """ Return a list of strings with VLAN IDs configured in the Kernel """
    from json import loads
    from vyos.utils.process import cmd

    if not interface.startswith('vxlan'):
        raise ValueError('Only applicable for VXLAN interfaces!')

    # Determine current OS Kernel configured VLANs
    #
    # $ bridge -j -p vlan tunnelshow dev vxlan0
    # [ {
    #         "ifname": "vxlan0",
    #         "tunnels": [ {
    #                 "vlan": 10,
    #                 "vlanEnd": 11,
    #                 "tunid": 10010,
    #                 "tunidEnd": 10011
    #             },{
    #                 "vlan": 20,
    #                 "tunid": 10020
    #             } ]
    #     } ]
    #
    os_configured_vlan_ids = []
    tmp = loads(cmd(f'bridge --json vlan tunnelshow dev {interface}'))
    if tmp:
        for tunnel in tmp[0].get('tunnels', {}):
            vlanStart = tunnel['vlan']
            if 'vlanEnd' in tunnel:
                vlanEnd = tunnel['vlanEnd']
                # Build a real list for user VLAN IDs
                vlan_list = list(range(vlanStart, vlanEnd +1))
                # Convert list of integers to list or strings
                os_configured_vlan_ids.extend(map(str, vlan_list))
                # Proceed with next tunnel - this one is complete
                continue

            # Add single tunel id - not part of a range
            os_configured_vlan_ids.append(str(vlanStart))

    return os_configured_vlan_ids

def get_vxlan_vni_filter(interface: str) -> list:
    """ Return a list of strings with VNIs configured in the Kernel"""
    from json import loads
    from vyos.utils.process import cmd

    if not interface.startswith('vxlan'):
        raise ValueError('Only applicable for VXLAN interfaces!')

    # Determine current OS Kernel configured VNI filters in VXLAN interface
    #
    # $ bridge -j vni show dev vxlan1
    # [{"ifname":"vxlan1","vnis":[{"vni":100},{"vni":200},{"vni":300,"vniEnd":399}]}]
    #
    # Example output: ['10010', '10020', '10021', '10022']
    os_configured_vnis = []
    tmp = loads(cmd(f'bridge --json vni show dev {interface}'))
    if tmp:
        for tunnel in tmp[0].get('vnis', {}):
            vniStart = tunnel['vni']
            if 'vniEnd' in tunnel:
                vniEnd = tunnel['vniEnd']
                # Build a real list for user VNIs
                vni_list = list(range(vniStart, vniEnd +1))
                # Convert list of integers to list or strings
                os_configured_vnis.extend(map(str, vni_list))
                # Proceed with next tunnel - this one is complete
                continue

            # Add single tunel id - not part of a range
            os_configured_vnis.append(str(vniStart))

    return os_configured_vnis

# Calculate prefix length of an IPv6 range, where possible
# Python-ified from source: https://gitlab.isc.org/isc-projects/dhcp/-/blob/master/keama/confparse.c#L4591
def ipv6_prefix_length(low, high):
    import socket

    bytemasks = [0x80, 0xc0, 0xe0, 0xf0, 0xf8, 0xfc, 0xfe, 0xff]

    try:
        lo = bytearray(socket.inet_pton(socket.AF_INET6, low))
        hi = bytearray(socket.inet_pton(socket.AF_INET6, high))
    except:
        return None

    xor = bytearray(a ^ b for a, b in zip(lo, hi))
        
    plen = 0
    while plen < 128 and xor[plen // 8] == 0:
        plen += 8
        
    if plen == 128:
        return plen
    
    for i in range((plen // 8) + 1, 16):
        if xor[i] != 0:
            return None
    
    for i in range(8):
        msk = ~xor[plen // 8] & 0xff
        
        if msk == bytemasks[i]:
            return plen + i + 1

    return None
