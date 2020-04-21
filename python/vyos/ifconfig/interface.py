# Copyright 2019 VyOS maintainers and contributors <maintainers@vyos.io>
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

import os
import re
import json
from copy import deepcopy

from ipaddress import IPv4Network
from ipaddress import IPv6Address
from ipaddress import IPv6Network
from netifaces import ifaddresses
# this is not the same as socket.AF_INET/INET6
from netifaces import AF_INET
from netifaces import AF_INET6

from vyos import ConfigError
from vyos.util import mac2eui64
from vyos.validate import is_ipv4
from vyos.validate import is_ipv6
from vyos.validate import is_intf_addr_assigned
from vyos.validate import assert_boolean
from vyos.validate import assert_list
from vyos.validate import assert_mac
from vyos.validate import assert_mtu
from vyos.validate import assert_positive
from vyos.validate import assert_range

from vyos.ifconfig.control import Control
from vyos.ifconfig.dhcp import DHCP
from vyos.ifconfig.vrrp import VRRP
from vyos.ifconfig.operational import Operational


class Interface(Control):
    # This is the class which will be used to create
    # self.operational, it allows subclasses, such as
    # WireGuard to modify their display behaviour
    OperationalClass = Operational

    options = ['debug', 'create',]
    required = []
    default = {
        'type': '',
        'debug': True,
        'create': True,
    }
    definition = {
        'section': '',
        'prefixes': [],
        'vlan': False,
        'bondable': False,
        'broadcast': False,
        'bridgeable':  False,
        'eternal': '',
    }

    _command_get = {
        'admin_state': {
            'shellcmd': 'ip -json link show dev {ifname}',
            'format': lambda j: 'up' if 'UP' in json.loads(j)[0]['flags'] else 'down',
        }
    }

    _command_set = {
        'admin_state': {
            'validate': lambda v: assert_list(v, ['up', 'down']),
            'shellcmd': 'ip link set dev {ifname} {value}',
        },
        'mac': {
            'validate': assert_mac,
            'shellcmd': 'ip link set dev {ifname} address {value}',
        },
        'vrf': {
            'convert': lambda v: f'master {v}' if v else 'nomaster',
            'shellcmd': 'ip link set dev {ifname} {value}',
        },
    }

    _sysfs_get = {
        'alias': {
            'location': '/sys/class/net/{ifname}/ifalias',
        },
        'mac': {
            'location': '/sys/class/net/{ifname}/address',
        },
        'mtu': {
            'location': '/sys/class/net/{ifname}/mtu',
        },
        'oper_state':{
            'location': '/sys/class/net/{ifname}/operstate',
        },
    }

    _sysfs_set = {
        'alias': {
            'convert': lambda name: name if name else '\0',
            'location': '/sys/class/net/{ifname}/ifalias',
        },
        'mtu': {
            'validate': assert_mtu,
            'location': '/sys/class/net/{ifname}/mtu',
        },
        'arp_cache_tmo': {
            'convert': lambda tmo: (int(tmo) * 1000),
            'location': '/proc/sys/net/ipv4/neigh/{ifname}/base_reachable_time_ms',
        },
        'arp_filter': {
            'validate': assert_boolean,
            'location': '/proc/sys/net/ipv4/conf/{ifname}/arp_filter',
        },
        'arp_accept': {
            'validate': lambda arp: assert_range(arp,0,2),
            'location': '/proc/sys/net/ipv4/conf/{ifname}/arp_accept',
        },
        'arp_announce': {
            'validate': assert_boolean,
            'location': '/proc/sys/net/ipv4/conf/{ifname}/arp_announce',
        },
        'arp_ignore': {
            'validate': assert_boolean,
            'location': '/proc/sys/net/ipv4/conf/{ifname}/arp_ignore',
        },
        'ipv6_autoconf': {
            'validate': lambda fwd: assert_range(fwd,0,2),
            'location': '/proc/sys/net/ipv6/conf/{ifname}/autoconf',
        },
        'ipv6_forwarding': {
            'validate': lambda fwd: assert_range(fwd,0,2),
            'location': '/proc/sys/net/ipv6/conf/{ifname}/forwarding',
        },
        'ipv6_dad_transmits': {
            'validate': assert_positive,
            'location': '/proc/sys/net/ipv6/conf/{ifname}/dad_transmits',
        },
        'proxy_arp': {
            'validate': assert_boolean,
            'location': '/proc/sys/net/ipv4/conf/{ifname}/proxy_arp',
        },
        'proxy_arp_pvlan': {
            'validate': assert_boolean,
            'location': '/proc/sys/net/ipv4/conf/{ifname}/proxy_arp_pvlan',
        },
        # link_detect vs link_filter name weirdness
        'link_detect': {
            'validate': lambda link: assert_range(link,0,3),
            'location': '/proc/sys/net/ipv4/conf/{ifname}/link_filter',
        },
    }

    @classmethod
    def exists(cls, ifname):
        return os.path.exists(f'/sys/class/net/{ifname}')

    def __init__(self, ifname, **kargs):
        """
        This is the base interface class which supports basic IP/MAC address
        operations as well as DHCP(v6). Other interface which represent e.g.
        and ethernet bridge are implemented as derived classes adding all
        additional functionality.

        For creation you will need to provide the interface type, otherwise
        the existing interface is used

        DEBUG:
        This class has embedded debugging (print) which can be enabled by
        creating the following file:
        vyos@vyos# touch /tmp/vyos.ifconfig.debug

        Example:
        >>> from vyos.ifconfig import Interface
        >>> i = Interface('eth0')
        """

        self.config = deepcopy(self.default)
        for k in self.options:
            if k in kargs:
                self.config[k] = kargs[k]

        # make sure the ifname is the first argument and not from the dict
        self.config['ifname'] = ifname

        # we must have updated config before initialising the Interface
        super().__init__(**kargs)
        self.ifname = ifname
        self.dhcp = DHCP(ifname)

        if not self.exists(ifname):
            # Any instance of Interface, such as Interface('eth0')
            # can be used safely to access the generic function in this class
            # as 'type' is unset, the class can not be created
            if not self.config['type']:
                raise Exception(f'interface "{ifname}" not found')

            # Should an Instance of a child class (EthernetIf, DummyIf, ..)
            # be required, then create should be set to False to not accidentally create it.
            # In case a subclass does not define it, we use get to set the default to True
            if self.config.get('create',True):
                for k in self.required:
                    if k not in kargs:
                        name = self.default['type']
                        raise ConfigError(f'missing required option {k} for {name} {ifname} creation')

                self._create()
            # If we can not connect to the interface then let the caller know
            # as the class could not be correctly initialised
            else:
                raise Exception('interface "{}" not found'.format(self.config['ifname']))

        # list of assigned IP addresses
        self._addr = []

        self.operational = self.OperationalClass(ifname)
        self.vrrp = VRRP(ifname)

    def _create(self):
        cmd = 'ip link add dev {ifname} type {type}'.format(**self.config)
        self._cmd(cmd)

    def remove(self):
        """
        Remove interface from operating system. Removing the interface
        deconfigures all assigned IP addresses and clear possible DHCP(v6)
        client processes.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> i = Interface('eth0')
        >>> i.remove()
        """
        # stop DHCP(v6) if running
        self.dhcp.v4.delete()
        self.dhcp.v6.delete()

        # remove all assigned IP addresses from interface - this is a bit redundant
        # as the kernel will remove all addresses on interface deletion, but we
        # can not delete ALL interfaces, see below
        for addr in self.get_addr():
            self.del_addr(addr)

        # ---------------------------------------------------------------------
        # Any class can define an eternal regex in its definition
        # interface matching the regex will not be deleted

        eternal = self.definition['eternal']
        if not eternal:
            self._delete()
        elif not re.match(eternal, self.ifname):
            self._delete()

    def _delete(self):
        # NOTE (Improvement):
        # after interface removal no other commands should be allowed
        # to be called and instead should raise an Exception:
        cmd = 'ip link del dev {}'.format(self.config['ifname'])
        return self._cmd(cmd)

    def get_mtu(self):
        """
        Get/set interface mtu in bytes.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').get_mtu()
        '1500'
        """
        return self.get_interface('mtu')

    def set_mtu(self, mtu):
        """
        Get/set interface mtu in bytes.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_mtu(1400)
        >>> Interface('eth0').get_mtu()
        '1400'
        """
        return self.set_interface('mtu', mtu)

    def get_mac(self):
        """
        Get current interface MAC (Media Access Contrl) address used.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').get_mac()
        '00:50:ab:cd:ef:00'
        """
        return self.get_interface('mac')

    def set_mac(self, mac):
        """
        Set interface MAC (Media Access Contrl) address to given value.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_mac('00:50:ab:cd:ef:01')
        """

        # If MAC is unchanged, bail out early
        if mac == self.get_mac():
            return None

        # MAC address can only be changed if interface is in 'down' state
        prev_state = self.get_admin_state()
        if prev_state == 'up':
            self.set_admin_state('down')

        self.set_interface('mac', mac)

    def set_vrf(self, vrf=''):
        """
        Add/Remove interface from given VRF instance.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_vrf('foo')
        >>> Interface('eth0').set_vrf()
        """
        self.set_interface('vrf', vrf)

    def set_arp_cache_tmo(self, tmo):
        """
        Set ARP cache timeout value in seconds. Internal Kernel representation
        is in milliseconds.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_arp_cache_tmo(40)
        """
        return self.set_interface('arp_cache_tmo', tmo)

    def set_arp_filter(self, arp_filter):
        """
        Filter ARP requests

        1 - Allows you to have multiple network interfaces on the same
            subnet, and have the ARPs for each interface be answered
            based on whether or not the kernel would route a packet from
            the ARP'd IP out that interface (therefore you must use source
            based routing for this to work). In other words it allows control
            of which cards (usually 1) will respond to an arp request.

        0 - (default) The kernel can respond to arp requests with addresses
            from other interfaces. This may seem wrong but it usually makes
            sense, because it increases the chance of successful communication.
            IP addresses are owned by the complete host on Linux, not by
            particular interfaces. Only for more complex setups like load-
            balancing, does this behaviour cause problems.
        """
        return self.set_interface('arp_filter', arp_filter)

    def set_arp_accept(self, arp_accept):
        """
        Define behavior for gratuitous ARP frames who's IP is not
        already present in the ARP table:
        0 - don't create new entries in the ARP table
        1 - create new entries in the ARP table

        Both replies and requests type gratuitous arp will trigger the
        ARP table to be updated, if this setting is on.

        If the ARP table already contains the IP address of the
        gratuitous arp frame, the arp table will be updated regardless
        if this setting is on or off.
        """
        return self.set_interface('arp_accept', arp_accept)

    def set_arp_announce(self, arp_announce):
        """
        Define different restriction levels for announcing the local
        source IP address from IP packets in ARP requests sent on
        interface:
        0 - (default) Use any local address, configured on any interface
        1 - Try to avoid local addresses that are not in the target's
            subnet for this interface. This mode is useful when target
            hosts reachable via this interface require the source IP
            address in ARP requests to be part of their logical network
            configured on the receiving interface. When we generate the
            request we will check all our subnets that include the
            target IP and will preserve the source address if it is from
            such subnet.

        Increasing the restriction level gives more chance for
        receiving answer from the resolved target while decreasing
        the level announces more valid sender's information.
        """
        return self.set_interface('arp_announce', arp_announce)

    def set_arp_ignore(self, arp_ignore):
        """
        Define different modes for sending replies in response to received ARP
        requests that resolve local target IP addresses:

        0 - (default): reply for any local target IP address, configured
            on any interface
        1 - reply only if the target IP address is local address
            configured on the incoming interface
        """
        return self.set_interface('arp_ignore', arp_ignore)

    def set_ipv6_autoconf(self, autoconf):
        """
        Autoconfigure addresses using Prefix Information in Router
        Advertisements.
        """
        return self.set_interface('ipv6_autoconf', autoconf)

    def set_ipv6_eui64_address(self, prefix):
        """
        Extended Unique Identifier (EUI), as per RFC2373, allows a host to
        assign iteslf a unique IPv6 address based on a given IPv6 prefix.

        If prefix is passed address is assigned, if prefix is '' address is
        removed from interface.
        """
        # if prefix is an empty string convert it to None so mac2eui64 works
        # as expected
        if not prefix:
            prefix = None

        eui64 = mac2eui64(self.get_mac(), prefix)

        if not prefix:
            # if prefix is empty - thus removed - we need to walk through all
            # interface IPv6 addresses and find the one with the calculated
            # EUI-64 identifier. The address is then removed
            for addr in self.get_addr():
                addr_wo_prefix = addr.split('/')[0]
                if is_ipv6(addr_wo_prefix):
                    if eui64 in IPv6Address(addr_wo_prefix).exploded:
                        self.del_addr(addr)

            return None

        # calculate and add EUI-64 IPv6 address
        if IPv6Network(prefix):
            # we also need to take the subnet length into account
            prefix = prefix.split('/')[1]
            eui64 = f'{eui64}/{prefix}'
            self.add_addr(eui64 )

    def set_ipv6_forwarding(self, forwarding):
        """
        Configure IPv6 interface-specific Host/Router behaviour.

        False:

        By default, Host behaviour is assumed.  This means:

        1. IsRouter flag is not set in Neighbour Advertisements.
        2. If accept_ra is TRUE (default), transmit Router
           Solicitations.
        3. If accept_ra is TRUE (default), accept Router
           Advertisements (and do autoconfiguration).
        4. If accept_redirects is TRUE (default), accept Redirects.

        True:

        If local forwarding is enabled, Router behaviour is assumed.
        This means exactly the reverse from the above:

        1. IsRouter flag is set in Neighbour Advertisements.
        2. Router Solicitations are not sent unless accept_ra is 2.
        3. Router Advertisements are ignored unless accept_ra is 2.
        4. Redirects are ignored.
        """
        return self.set_interface('ipv6_forwarding', forwarding)

    def set_ipv6_dad_messages(self, dad):
        """
        The amount of Duplicate Address Detection probes to send.
        Default: 1
        """
        return self.set_interface('ipv6_dad_transmits', dad)

    def set_link_detect(self, link_filter):
        """
        Configure kernel response in packets received on interfaces that are 'down'

        0 - Allow packets to be received for the address on this interface
            even if interface is disabled or no carrier.

        1 - Ignore packets received if interface associated with the incoming
            address is down.

        2 - Ignore packets received if interface associated with the incoming
            address is down or has no carrier.

        Default value is 0. Note that some distributions enable it in startup
        scripts.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_link_detect(1)
        """
        return self.set_interface('link_detect', link_filter)

    def get_alias(self):
        """
        Get interface alias name used by e.g. SNMP

        Example:
        >>> Interface('eth0').get_alias()
        'interface description as set by user'
        """
        return self.get_interface('alias')

    def set_alias(self, ifalias=''):
        """
        Set interface alias name used by e.g. SNMP

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_alias('VyOS upstream interface')

        to clear alias e.g. delete it use:

        >>> Interface('eth0').set_ifalias('')
        """
        self.set_interface('alias', ifalias)

    def get_admin_state(self):
        """
        Get interface administrative state. Function will return 'up' or 'down'

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').get_admin_state()
        'up'
        """
        return self.get_interface('admin_state')

    def set_admin_state(self, state):
        """
        Set interface administrative state to be 'up' or 'down'

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_admin_state('down')
        >>> Interface('eth0').get_admin_state()
        'down'
        """
        return self.set_interface('admin_state', state)

    def set_proxy_arp(self, enable):
        """
        Set per interface proxy ARP configuration

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_proxy_arp(1)
        """
        self.set_interface('proxy_arp', enable)

    def set_proxy_arp_pvlan(self, enable):
        """
        Private VLAN proxy arp.
        Basically allow proxy arp replies back to the same interface
        (from which the ARP request/solicitation was received).

        This is done to support (ethernet) switch features, like RFC
        3069, where the individual ports are NOT allowed to
        communicate with each other, but they are allowed to talk to
        the upstream router.  As described in RFC 3069, it is possible
        to allow these hosts to communicate through the upstream
        router by proxy_arp'ing. Don't need to be used together with
        proxy_arp.

        This technology is known by different names:
        In RFC 3069 it is called VLAN Aggregation.
        Cisco and Allied Telesyn call it Private VLAN.
        Hewlett-Packard call it Source-Port filtering or port-isolation.
        Ericsson call it MAC-Forced Forwarding (RFC Draft).

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_proxy_arp_pvlan(1)
        """
        self.set_interface('proxy_arp_pvlan', enable)

    def get_addr(self):
        """
        Retrieve assigned IPv4 and IPv6 addresses from given interface.
        This is done using the netifaces and ipaddress python modules.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').get_addrs()
        ['172.16.33.30/24', 'fe80::20c:29ff:fe11:a174/64']
        """

        ipv4 = []
        ipv6 = []

        if AF_INET in ifaddresses(self.config['ifname']).keys():
            for v4_addr in ifaddresses(self.config['ifname'])[AF_INET]:
                # we need to manually assemble a list of IPv4 address/prefix
                prefix = '/' + \
                    str(IPv4Network('0.0.0.0/' + v4_addr['netmask']).prefixlen)
                ipv4.append(v4_addr['addr'] + prefix)

        if AF_INET6 in ifaddresses(self.config['ifname']).keys():
            for v6_addr in ifaddresses(self.config['ifname'])[AF_INET6]:
                # Note that currently expanded netmasks are not supported. That means
                # 2001:db00::0/24 is a valid argument while 2001:db00::0/ffff:ff00:: not.
                # see https://docs.python.org/3/library/ipaddress.html
                bits = bin(
                    int(v6_addr['netmask'].replace(':', ''), 16)).count('1')
                prefix = '/' + str(bits)

                # we alsoneed to remove the interface suffix on link local
                # addresses
                v6_addr['addr'] = v6_addr['addr'].split('%')[0]
                ipv6.append(v6_addr['addr'] + prefix)

        return ipv4 + ipv6

    def add_addr(self, addr):
        """
        Add IP(v6) address to interface. Address is only added if it is not
        already assigned to that interface.

        addr: can be an IPv4 address, IPv6 address, dhcp or dhcpv6!
              IPv4: add IPv4 address to interface
              IPv6: add IPv6 address to interface
              dhcp: start dhclient (IPv4) on interface
              dhcpv6: start dhclient (IPv6) on interface

        Example:
        >>> from vyos.ifconfig import Interface
        >>> j = Interface('eth0')
        >>> j.add_addr('192.0.2.1/24')
        >>> j.add_addr('2001:db8::ffff/64')
        >>> j.get_addr()
        ['192.0.2.1/24', '2001:db8::ffff/64']
        """

        # cache new IP address which is assigned to interface
        self._addr.append(addr)

        # we can not have both DHCP and static IPv4 addresses assigned to an interface
        if 'dhcp' in self._addr:
            for addr in self._addr:
                # do not change below 'if' ordering esle you will get an exception as:
                #   ValueError: 'dhcp' does not appear to be an IPv4 or IPv6 address
                if addr != 'dhcp' and is_ipv4(addr):
                    raise ConfigError(
                        "Can't configure both static IPv4 and DHCP address on the same interface")

        if addr == 'dhcp':
            self.dhcp.v4.set()
        elif addr == 'dhcpv6':
            self.dhcp.v6.set()
        else:
            if not is_intf_addr_assigned(self.config['ifname'], addr):
                cmd = 'ip addr add "{}" dev "{}"'.format(addr, self.config['ifname'])
                return self._cmd(cmd)

    def del_addr(self, addr):
        """
        Delete IP(v6) address to interface. Address is only added if it is
        assigned to that interface.

        addr: can be an IPv4 address, IPv6 address, dhcp or dhcpv6!
              IPv4: delete IPv4 address from interface
              IPv6: delete IPv6 address from interface
              dhcp: stop dhclient (IPv4) on interface
              dhcpv6: stop dhclient (IPv6) on interface

        Example:
        >>> from vyos.ifconfig import Interface
        >>> j = Interface('eth0')
        >>> j.add_addr('2001:db8::ffff/64')
        >>> j.add_addr('192.0.2.1/24')
        >>> j.get_addr()
        ['192.0.2.1/24', '2001:db8::ffff/64']
        >>> j.del_addr('192.0.2.1/24')
        >>> j.get_addr()
        ['2001:db8::ffff/64']
        """
        if addr == 'dhcp':
            self.dhcp.v4.delete()
        elif addr == 'dhcpv6':
            self.dhcp.v6.delete()
        else:
            if is_intf_addr_assigned(self.config['ifname'], addr):
                cmd = 'ip addr del "{}" dev "{}"'.format(addr, self.config['ifname'])
                return self._cmd(cmd)
