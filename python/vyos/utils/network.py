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

def interface_exists_in_netns(interface_name, netns):
    from vyos.utils.process import rc_cmd
    rc, out = rc_cmd(f'ip netns exec {netns} ip link show dev {interface_name}')
    if rc == 0:
        return True
    return False

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
    import os
    if not os.path.exists(f'/sys/class/net/{interface}'):
        return None
    from json import loads
    from vyos.utils.process import cmd
    tmp = loads(cmd(f'ip --detail --json link show dev {interface}'))[0]
    return tmp

def get_interface_address(interface):
    """ Returns the used encapsulation protocol for given interface.
        If interface does not exist, None is returned.
    """
    import os
    if not os.path.exists(f'/sys/class/net/{interface}'):
        return None
    from json import loads
    from vyos.utils.process import cmd
    tmp = loads(cmd(f'ip --detail --json addr show dev {interface}'))[0]
    return tmp

def get_interface_namespace(iface):
    """
       Returns wich netns the interface belongs to
    """
    from json import loads
    from vyos.utils.process import cmd
    # Check if netns exist
    tmp = loads(cmd(f'ip --json netns ls'))
    if len(tmp) == 0:
        return None

    for ns in tmp:
        netns = f'{ns["name"]}'
        # Search interface in each netns
        data = loads(cmd(f'ip netns exec {netns} ip --json link show'))
        for tmp in data:
            if iface == tmp["ifname"]:
                return netns

def is_wwan_connected(interface):
    """ Determine if a given WWAN interface, e.g. wwan0 is connected to the
    carrier network or not """
    import json
    from vyos.utils.process import cmd

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
    import os
    if not os.path.exists(f'/sys/class/net/{interface}'):
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

def is_addr_assigned(ip_address, vrf=None) -> bool:
    """ Verify if the given IPv4/IPv6 address is assigned to any interface """
    from netifaces import interfaces
    from vyos.utils.network import get_interface_config
    from vyos.utils.dict import dict_search

    for interface in interfaces():
        # Check if interface belongs to the requested VRF, if this is not the
        # case there is no need to proceed with this data set - continue loop
        # with next element
        tmp = get_interface_config(interface)
        if dict_search('master', tmp) != vrf:
            continue

        if is_intf_addr_assigned(interface, ip_address):
            return True

    return False

def is_intf_addr_assigned(intf, address) -> bool:
    """
    Verify if the given IPv4/IPv6 address is assigned to specific interface.
    It can check both a single IP address (e.g. 192.0.2.1 or a assigned CIDR
    address 192.0.2.1/24.
    """
    from vyos.template import is_ipv4

    from netifaces import ifaddresses
    from netifaces import AF_INET
    from netifaces import AF_INET6

    # check if the requested address type is configured at all
    # {
    # 17: [{'addr': '08:00:27:d9:5b:04', 'broadcast': 'ff:ff:ff:ff:ff:ff'}],
    # 2:  [{'addr': '10.0.2.15', 'netmask': '255.255.255.0', 'broadcast': '10.0.2.255'}],
    # 10: [{'addr': 'fe80::a00:27ff:fed9:5b04%eth0', 'netmask': 'ffff:ffff:ffff:ffff::'}]
    # }
    try:
        addresses = ifaddresses(intf)
    except ValueError as e:
        print(e)
        return False

    # determine IP version (AF_INET or AF_INET6) depending on passed address
    addr_type = AF_INET if is_ipv4(address) else AF_INET6

    # Check every IP address on this interface for a match
    netmask = None
    if '/' in address:
        address, netmask = address.split('/')
    for ip in addresses.get(addr_type, []):
        # ip can have the interface name in the 'addr' field, we need to remove it
        # {'addr': 'fe80::a00:27ff:fec5:f821%eth2', 'netmask': 'ffff:ffff:ffff:ffff::'}
        ip_addr = ip['addr'].split('%')[0]

        if not _are_same_ip(address, ip_addr):
            continue

        # we do not have a netmask to compare against, they are the same
        if not netmask:
            return True

        prefixlen = ''
        if is_ipv4(ip_addr):
            prefixlen = sum([bin(int(_)).count('1') for _ in ip['netmask'].split('.')])
        else:
            prefixlen = sum([bin(int(_,16)).count('1') for _ in ip['netmask'].split('/')[0].split(':') if _])

        if str(prefixlen) == netmask:
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

def is_afi_configured(interface, afi):
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
