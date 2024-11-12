# Copyright 2019-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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
import jmespath

from copy import deepcopy
from glob import glob

from ipaddress import IPv4Network
from netifaces import ifaddresses
# this is not the same as socket.AF_INET/INET6
from netifaces import AF_INET
from netifaces import AF_INET6

from vyos import ConfigError
from vyos.configdict import list_diff
from vyos.configdict import dict_merge
from vyos.configdict import get_vlan_ids
from vyos.defaults import directories
from vyos.pki import find_chain
from vyos.pki import encode_certificate
from vyos.pki import load_certificate
from vyos.pki import wrap_private_key
from vyos.template import is_ipv4
from vyos.template import is_ipv6
from vyos.template import render
from vyos.utils.network import mac2eui64
from vyos.utils.dict import dict_search
from vyos.utils.network import get_interface_config
from vyos.utils.network import get_interface_namespace
from vyos.utils.network import get_vrf_tableid
from vyos.utils.network import is_netns_interface
from vyos.utils.process import is_systemd_service_active
from vyos.utils.process import run
from vyos.utils.file import read_file
from vyos.utils.file import write_file
from vyos.utils.network import is_intf_addr_assigned
from vyos.utils.network import is_ipv6_link_local
from vyos.utils.assertion import assert_boolean
from vyos.utils.assertion import assert_list
from vyos.utils.assertion import assert_mac
from vyos.utils.assertion import assert_mtu
from vyos.utils.assertion import assert_positive
from vyos.utils.assertion import assert_range
from vyos.ifconfig.control import Control
from vyos.ifconfig.vrrp import VRRP
from vyos.ifconfig.operational import Operational
from vyos.ifconfig import Section

from netaddr import EUI
from netaddr import mac_unix_expanded

link_local_prefix = 'fe80::/64'

class Interface(Control):
    # This is the class which will be used to create
    # self.operational, it allows subclasses, such as
    # WireGuard to modify their display behaviour
    OperationalClass = Operational

    options = ['debug', 'create']
    required = []
    default = {
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
            'format': lambda j: 'up' if 'UP' in jmespath.search('[*].flags | [0]', json.loads(j)) else 'down',
        },
        'alias': {
            'shellcmd': 'ip -json -detail link list dev {ifname}',
            'format': lambda j: jmespath.search('[*].ifalias | [0]', json.loads(j)) or '',
        },
        'ifindex': {
            'shellcmd': 'ip -json -detail link list dev {ifname}',
            'format': lambda j: jmespath.search('[*].ifindex | [0]', json.loads(j)) or '',
        },
        'mac': {
            'shellcmd': 'ip -json -detail link list dev {ifname}',
            'format': lambda j: jmespath.search('[*].address | [0]', json.loads(j)),
        },
        'min_mtu': {
            'shellcmd': 'ip -json -detail link list dev {ifname}',
            'format': lambda j: jmespath.search('[*].min_mtu | [0]', json.loads(j)),
        },
        'max_mtu': {
            'shellcmd': 'ip -json -detail link list dev {ifname}',
            'format': lambda j: jmespath.search('[*].max_mtu | [0]', json.loads(j)),
        },
        'mtu': {
            'shellcmd': 'ip -json -detail link list dev {ifname}',
            'format': lambda j: jmespath.search('[*].mtu | [0]', json.loads(j)),
        },
        'oper_state': {
            'shellcmd': 'ip -json -detail link list dev {ifname}',
            'format': lambda j: jmespath.search('[*].operstate | [0]', json.loads(j)),
        },
        'vrf': {
            'shellcmd': 'ip -json -detail link list dev {ifname}',
            'format': lambda j: jmespath.search('[?linkinfo.info_slave_kind == `vrf`].master | [0]', json.loads(j)),
        },
    }

    _command_set = {
        'admin_state': {
            'validate': lambda v: assert_list(v, ['up', 'down']),
            'shellcmd': 'ip link set dev {ifname} {value}',
        },
        'alias': {
            'convert': lambda name: name if name else '',
            'shellcmd': 'ip link set dev {ifname} alias "{value}"',
        },
        'bridge_port_isolation': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'shellcmd': 'bridge link set dev {ifname} isolated {value}',
        },
        'mac': {
            'validate': assert_mac,
            'shellcmd': 'ip link set dev {ifname} address {value}',
        },
        'mtu': {
            'validate': assert_mtu,
            'shellcmd': 'ip link set dev {ifname} mtu {value}',
        },
        'vrf': {
            'convert': lambda v: f'master {v}' if v else 'nomaster',
            'shellcmd': 'ip link set dev {ifname} {value}',
        },
    }

    _sysfs_set = {
        'arp_cache_tmo': {
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
        'ipv4_forwarding': {
            'validate': assert_boolean,
            'location': '/proc/sys/net/ipv4/conf/{ifname}/forwarding',
        },
        'ipv4_directed_broadcast': {
            'validate': assert_boolean,
            'location': '/proc/sys/net/ipv4/conf/{ifname}/bc_forwarding',
        },
        'ipv6_accept_ra': {
            'validate': lambda ara: assert_range(ara,0,3),
            'location': '/proc/sys/net/ipv6/conf/{ifname}/accept_ra',
        },
        'ipv6_autoconf': {
            'validate': lambda aco: assert_range(aco,0,2),
            'location': '/proc/sys/net/ipv6/conf/{ifname}/autoconf',
        },
        'ipv6_forwarding': {
            'validate': lambda fwd: assert_range(fwd,0,2),
            'location': '/proc/sys/net/ipv6/conf/{ifname}/forwarding',
        },
        'ipv6_accept_dad': {
            'validate': lambda dad: assert_range(dad,0,3),
            'location': '/proc/sys/net/ipv6/conf/{ifname}/accept_dad',
        },
        'ipv6_dad_transmits': {
            'validate': assert_positive,
            'location': '/proc/sys/net/ipv6/conf/{ifname}/dad_transmits',
        },
        'ipv6_cache_tmo': {
            'location': '/proc/sys/net/ipv6/neigh/{ifname}/base_reachable_time_ms',
        },
        'path_cost': {
            # XXX: we should set a maximum
            'validate': assert_positive,
            'location': '/sys/class/net/{ifname}/brport/path_cost',
            'errormsg': '{ifname} is not a bridge port member'
        },
        'path_priority': {
            # XXX: we should set a maximum
            'validate': assert_positive,
            'location': '/sys/class/net/{ifname}/brport/priority',
            'errormsg': '{ifname} is not a bridge port member'
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
        'per_client_thread': {
            'validate': assert_boolean,
            'location': '/sys/class/net/{ifname}/threaded',
        },
    }

    _sysfs_get = {
        'arp_cache_tmo': {
            'location': '/proc/sys/net/ipv4/neigh/{ifname}/base_reachable_time_ms',
        },
        'arp_filter': {
            'location': '/proc/sys/net/ipv4/conf/{ifname}/arp_filter',
        },
        'arp_accept': {
            'location': '/proc/sys/net/ipv4/conf/{ifname}/arp_accept',
        },
        'arp_announce': {
            'location': '/proc/sys/net/ipv4/conf/{ifname}/arp_announce',
        },
        'arp_ignore': {
            'location': '/proc/sys/net/ipv4/conf/{ifname}/arp_ignore',
        },
        'ipv4_forwarding': {
            'location': '/proc/sys/net/ipv4/conf/{ifname}/forwarding',
        },
        'ipv4_directed_broadcast': {
            'location': '/proc/sys/net/ipv4/conf/{ifname}/bc_forwarding',
        },
        'ipv6_accept_ra': {
            'location': '/proc/sys/net/ipv6/conf/{ifname}/accept_ra',
        },
        'ipv6_autoconf': {
            'location': '/proc/sys/net/ipv6/conf/{ifname}/autoconf',
        },
        'ipv6_forwarding': {
            'location': '/proc/sys/net/ipv6/conf/{ifname}/forwarding',
        },
        'ipv6_accept_dad': {
            'location': '/proc/sys/net/ipv6/conf/{ifname}/accept_dad',
        },
        'ipv6_dad_transmits': {
            'location': '/proc/sys/net/ipv6/conf/{ifname}/dad_transmits',
        },
        'ipv6_cache_tmo': {
            'location': '/proc/sys/net/ipv6/neigh/{ifname}/base_reachable_time_ms',
        },
        'proxy_arp': {
            'location': '/proc/sys/net/ipv4/conf/{ifname}/proxy_arp',
        },
        'proxy_arp_pvlan': {
            'location': '/proc/sys/net/ipv4/conf/{ifname}/proxy_arp_pvlan',
        },
        'link_detect': {
            'location': '/proc/sys/net/ipv4/conf/{ifname}/link_filter',
        },
        'per_client_thread': {
            'validate': assert_boolean,
            'location': '/sys/class/net/{ifname}/threaded',
        },
    }

    @classmethod
    def exists(cls, ifname: str, netns: str=None) -> bool:
        cmd = f'ip link show dev {ifname}'
        if netns:
           cmd = f'ip netns exec {netns} {cmd}'
        return run(cmd) == 0

    @classmethod
    def get_config(cls):
        """
        Some but not all interfaces require a configuration when they are added
        using iproute2. This method will provide the configuration dictionary
        used by this class.
        """
        return deepcopy(cls.default)

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
        self.config = deepcopy(kargs)
        self.config['ifname'] = self.ifname = ifname

        self._admin_state_down_cnt = 0

        # we must have updated config before initialising the Interface
        super().__init__(**kargs)

        if not self.exists(ifname):
            # Any instance of Interface, such as Interface('eth0') can be used
            # safely to access the generic function in this class as 'type' is
            # unset, the class can not be created
            if not self.iftype:
                raise Exception(f'interface "{ifname}" not found')
            self.config['type'] = self.iftype

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
                raise Exception(f'interface "{ifname}" not found!')

        # temporary list of assigned IP addresses
        self._addr = []

        self.operational = self.OperationalClass(ifname)
        self.vrrp = VRRP(ifname)

    def _create(self):
        # Do not create interface that already exist or exists in netns
        netns = self.config.get('netns', None)
        if self.exists(f'{self.ifname}', netns=netns):
            return

        cmd = 'ip link add dev {ifname} type {type}'.format(**self.config)
        if 'netns' in self.config: cmd = f'ip netns exec {netns} {cmd}'
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
        # Stop WPA supplicant if EAPoL was in use
        if is_systemd_service_active(f'wpa_supplicant-wired@{self.ifname}'):
            self._cmd(f'systemctl stop wpa_supplicant-wired@{self.ifname}')

        # remove all assigned IP addresses from interface - this is a bit redundant
        # as the kernel will remove all addresses on interface deletion, but we
        # can not delete ALL interfaces, see below
        self.flush_addrs()

        # remove interface from conntrack VRF interface map
        self._del_interface_from_ct_iface_map()

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
        cmd = 'ip link del dev {ifname}'.format(**self.config)
        # for delete we can't get data from self.config{'netns'}
        netns = get_interface_namespace(self.ifname)
        if netns: cmd = f'ip netns exec {netns} {cmd}'
        return self._cmd(cmd)

    def _nft_check_and_run(self, nft_command):
        # Check if deleting is possible first to avoid raising errors
        _, err = self._popen(f'nft --check {nft_command}')
        if not err:
            # Remove map element
            self._cmd(f'nft {nft_command}')

    def _del_interface_from_ct_iface_map(self):
        nft_command = f'delete element inet vrf_zones ct_iface_map {{ "{self.ifname}" }}'
        self._nft_check_and_run(nft_command)

    def _add_interface_to_ct_iface_map(self, vrf_table_id: int):
        nft_command = f'add element inet vrf_zones ct_iface_map {{ "{self.ifname}" : {vrf_table_id} }}'
        self._nft_check_and_run(nft_command)

    def get_ifindex(self):
        """
        Get interface index by name

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').get_ifindex()
        '2'
        """
        return int(self.get_interface('ifindex'))

    def get_min_mtu(self):
        """
        Get hardware minimum supported MTU

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').get_min_mtu()
        '60'
        """
        return int(self.get_interface('min_mtu'))

    def get_max_mtu(self):
        """
        Get hardware maximum supported MTU

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').get_max_mtu()
        '9000'
        """
        return int(self.get_interface('max_mtu'))

    def get_mtu(self):
        """
        Get/set interface mtu in bytes.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').get_mtu()
        '1500'
        """
        return int(self.get_interface('mtu'))

    def set_mtu(self, mtu):
        """
        Get/set interface mtu in bytes.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_mtu(1400)
        >>> Interface('eth0').get_mtu()
        '1400'
        """
        tmp = self.get_interface('mtu')
        if str(tmp) == mtu:
            return None
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

    def get_mac_synthetic(self):
        """
        Get a synthetic MAC address. This is a common method which can be called
        from derived classes to overwrite the get_mac() call in a generic way.

        NOTE: Tunnel interfaces have no "MAC" address by default. The content
              of the 'address' file in /sys/class/net/device contains the
              local-ip thus we generate a random MAC address instead

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').get_mac()
        '00:50:ab:cd:ef:00'
        """
        from hashlib import sha256

        # Get processor ID number
        cpu_id = self._cmd('sudo dmidecode -t 4 | grep ID | head -n1 | sed "s/.*ID://;s/ //g"')

        # XXX: T3894 - it seems not all systems have eth0 - get a list of all
        # available Ethernet interfaces on the system (without VLAN subinterfaces)
        # and then take the first one.
        all_eth_ifs = Section.interfaces('ethernet', vlan=False)
        first_mac = Interface(all_eth_ifs[0]).get_mac()

        sha = sha256()
        # Calculate SHA256 sum based on the CPU ID number, eth0 mac address and
        # this interface identifier - this is as predictable as an interface
        # MAC address and thus can be used in the same way
        sha.update(cpu_id.encode())
        sha.update(first_mac.encode())
        sha.update(self.ifname.encode())
        # take the most significant 48 bits from the SHA256 string
        tmp = sha.hexdigest()[:12]
        # Convert pseudo random string into EUI format which now represents a
        # MAC address
        tmp = EUI(tmp).value
        # set locally administered bit in MAC address
        tmp |= 0xf20000000000
        # convert integer to "real" MAC address representation
        mac = EUI(hex(tmp).split('x')[-1])
        # change dialect to use : as delimiter instead of -
        mac.dialect = mac_unix_expanded
        return str(mac)

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

        # Turn an interface to the 'up' state if it was changed to 'down' by this fucntion
        if prev_state == 'up':
            self.set_admin_state('up')

    def del_netns(self, netns: str) -> bool:
        """ Remove interface from given network namespace """
        # If network namespace does not exist then there is nothing to delete
        if not os.path.exists(f'/run/netns/{netns}'):
            return False

        # Check if interface exists in network namespace
        if is_netns_interface(self.ifname, netns):
            self._cmd(f'ip netns exec {netns} ip link del dev {self.ifname}')
            return True
        return False

    def set_netns(self, netns: str) -> bool:
        """
        Add interface from given network namespace

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('dum0').set_netns('foo')
        """
        self._cmd(f'ip link set dev {self.ifname} netns {netns}')
        return True

    def get_vrf(self):
        """
        Get VRF from interface

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').get_vrf()
        """
        return self.get_interface('vrf')

    def set_vrf(self, vrf: str) -> bool:
        """
        Add/Remove interface from given VRF instance.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_vrf('foo')
        >>> Interface('eth0').set_vrf()
        """

        # Don't allow for netns yet
        if 'netns' in self.config:
            return False

        tmp = self.get_interface('vrf')
        if tmp == vrf:
            return False

        # Get current VRF table ID
        old_vrf_tableid = get_vrf_tableid(self.ifname)
        self.set_interface('vrf', vrf)

        if vrf:
            # Get routing table ID number for VRF
            vrf_table_id = get_vrf_tableid(vrf)
            # Add map element with interface and zone ID
            if vrf_table_id:
                # delete old table ID from nftables if it has changed, e.g. interface moved to a different VRF
                if old_vrf_tableid and old_vrf_tableid != int(vrf_table_id):
                    self._del_interface_from_ct_iface_map()
                self._add_interface_to_ct_iface_map(vrf_table_id)
        else:
            self._del_interface_from_ct_iface_map()

        return True

    def set_arp_cache_tmo(self, tmo):
        """
        Set ARP cache timeout value in seconds. Internal Kernel representation
        is in milliseconds.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_arp_cache_tmo(40)
        """
        tmo = str(int(tmo) * 1000)
        tmp = self.get_interface('arp_cache_tmo')
        if tmp == tmo:
            return None
        return self.set_interface('arp_cache_tmo', tmo)

    def set_ipv6_cache_tmo(self, tmo):
        """
        Set IPv6 cache timeout value in seconds. Internal Kernel representation
        is in milliseconds.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_ipv6_cache_tmo(40)
        """
        tmo = str(int(tmo) * 1000)
        tmp = self.get_interface('ipv6_cache_tmo')
        if tmp == tmo:
            return None
        return self.set_interface('ipv6_cache_tmo', tmo)

    def _cleanup_mss_rules(self, table, ifname):
        commands = []
        results = self._cmd(f'nft -a list chain {table} VYOS_TCP_MSS').split("\n")
        for line in results:
            if f'oifname "{ifname}"' in line:
                handle_search = re.search('handle (\d+)', line)
                if handle_search:
                    self._cmd(f'nft delete rule {table} VYOS_TCP_MSS handle {handle_search[1]}')

    def set_tcp_ipv4_mss(self, mss):
        """
        Set IPv4 TCP MSS value advertised when TCP SYN packets leave this
        interface. Value is in bytes.

        A value of 0 will disable the MSS adjustment

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_tcp_ipv4_mss(1340)
        """
        # Don't allow for netns yet
        if 'netns' in self.config:
            return None

        self._cleanup_mss_rules('raw', self.ifname)
        nft_prefix = 'nft add rule raw VYOS_TCP_MSS'
        base_cmd = f'oifname "{self.ifname}" tcp flags & (syn|rst) == syn'
        if mss == 'clamp-mss-to-pmtu':
            self._cmd(f"{nft_prefix} '{base_cmd} tcp option maxseg size set rt mtu'")
        elif int(mss) > 0:
            low_mss = str(int(mss) + 1)
            self._cmd(f"{nft_prefix} '{base_cmd} tcp option maxseg size {low_mss}-65535 tcp option maxseg size set {mss}'")

    def set_tcp_ipv6_mss(self, mss):
        """
        Set IPv6 TCP MSS value advertised when TCP SYN packets leave this
        interface. Value is in bytes.

        A value of 0 will disable the MSS adjustment

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_tcp_mss(1320)
        """
        # Don't allow for netns yet
        if 'netns' in self.config:
            return None

        self._cleanup_mss_rules('ip6 raw', self.ifname)
        nft_prefix = 'nft add rule ip6 raw VYOS_TCP_MSS'
        base_cmd = f'oifname "{self.ifname}" tcp flags & (syn|rst) == syn'
        if mss == 'clamp-mss-to-pmtu':
            self._cmd(f"{nft_prefix} '{base_cmd} tcp option maxseg size set rt mtu'")
        elif int(mss) > 0:
            low_mss = str(int(mss) + 1)
            self._cmd(f"{nft_prefix} '{base_cmd} tcp option maxseg size {low_mss}-65535 tcp option maxseg size set {mss}'")

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
        tmp = self.get_interface('arp_filter')
        if tmp == arp_filter:
            return None
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
        tmp = self.get_interface('arp_accept')
        if tmp == arp_accept:
            return None
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
        tmp = self.get_interface('arp_announce')
        if tmp == arp_announce:
            return None
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
        tmp = self.get_interface('arp_ignore')
        if tmp == arp_ignore:
            return None
        return self.set_interface('arp_ignore', arp_ignore)

    def set_ipv4_forwarding(self, forwarding):
        """ Configure IPv4 forwarding. """
        tmp = self.get_interface('ipv4_forwarding')
        if tmp == forwarding:
            return None
        return self.set_interface('ipv4_forwarding', forwarding)

    def set_ipv4_directed_broadcast(self, forwarding):
        """ Configure IPv4 directed broadcast forwarding. """
        tmp = self.get_interface('ipv4_directed_broadcast')
        if tmp == forwarding:
            return None
        return self.set_interface('ipv4_directed_broadcast', forwarding)

    def _cleanup_ipv4_source_validation_rules(self, ifname):
        results = self._cmd(f'nft -a list chain ip raw vyos_rpfilter').split("\n")
        for line in results:
            if f'iifname "{ifname}"' in line:
                handle_search = re.search('handle (\d+)', line)
                if handle_search:
                    self._cmd(f'nft delete rule ip raw vyos_rpfilter handle {handle_search[1]}')

    def set_ipv4_source_validation(self, mode):
        """
        Set IPv4 reverse path validation

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_ipv4_source_validation('strict')
        """
        # Don't allow for netns yet
        if 'netns' in self.config:
            return None

        self._cleanup_ipv4_source_validation_rules(self.ifname)
        nft_prefix = f'nft insert rule ip raw vyos_rpfilter iifname "{self.ifname}"'
        if mode in ['strict', 'loose']:
            self._cmd(f"{nft_prefix} counter return")
        if mode == 'strict':
            self._cmd(f"{nft_prefix} fib saddr . iif oif 0 counter drop")
        elif mode == 'loose':
            self._cmd(f"{nft_prefix} fib saddr oif 0 counter drop")

    def _cleanup_ipv6_source_validation_rules(self, ifname):
        results = self._cmd(f'nft -a list chain ip6 raw vyos_rpfilter').split("\n")
        for line in results:
            if f'iifname "{ifname}"' in line:
                handle_search = re.search('handle (\d+)', line)
                if handle_search:
                    self._cmd(f'nft delete rule ip6 raw vyos_rpfilter handle {handle_search[1]}')

    def set_ipv6_source_validation(self, mode):
        """
        Set IPv6 reverse path validation

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_ipv6_source_validation('strict')
        """
        # Don't allow for netns yet
        if 'netns' in self.config:
            return None

        self._cleanup_ipv6_source_validation_rules(self.ifname)
        nft_prefix = f'nft insert rule ip6 raw vyos_rpfilter iifname "{self.ifname}"'
        if mode in ['strict', 'loose']:
            self._cmd(f"{nft_prefix} counter return")
        if mode == 'strict':
            self._cmd(f"{nft_prefix} fib saddr . iif oif 0 counter drop")
        elif mode == 'loose':
            self._cmd(f"{nft_prefix} fib saddr oif 0 counter drop")

    def set_ipv6_accept_ra(self, accept_ra):
        """
        Accept Router Advertisements; autoconfigure using them.

        It also determines whether or not to transmit Router Solicitations.
        If and only if the functional setting is to accept Router
        Advertisements, Router Solicitations will be transmitted.

        0 - Do not accept Router Advertisements.
        1 - (default) Accept Router Advertisements if forwarding is disabled.
        2 - Overrule forwarding behaviour. Accept Router Advertisements even if
            forwarding is enabled.
        """
        tmp = self.get_interface('ipv6_accept_ra')
        if tmp == accept_ra:
            return None
        return self.set_interface('ipv6_accept_ra', accept_ra)

    def set_ipv6_autoconf(self, autoconf):
        """
        Autoconfigure addresses using Prefix Information in Router
        Advertisements.
        """
        tmp = self.get_interface('ipv6_autoconf')
        if tmp == autoconf:
            return None
        return self.set_interface('ipv6_autoconf', autoconf)

    def add_ipv6_eui64_address(self, prefix):
        """
        Extended Unique Identifier (EUI), as per RFC2373, allows a host to
        assign itself a unique IPv6 address based on a given IPv6 prefix.

        Calculate the EUI64 from the interface's MAC, then assign it
        with the given prefix to the interface.
        """
        # T2863: only add a link-local IPv6 address if the interface returns
        # a MAC address. This is not the case on e.g. WireGuard interfaces.
        mac = self.get_mac()
        if mac:
            eui64 = mac2eui64(mac, prefix)
            prefixlen = prefix.split('/')[1]
            self.add_addr(f'{eui64}/{prefixlen}')

    def del_ipv6_eui64_address(self, prefix):
        """
        Delete the address based on the interface's MAC-based EUI64
        combined with the prefix address.
        """
        if is_ipv6(prefix):
            eui64 = mac2eui64(self.get_mac(), prefix)
            prefixlen = prefix.split('/')[1]
            self.del_addr(f'{eui64}/{prefixlen}')

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
        tmp = self.get_interface('ipv6_forwarding')
        if tmp == forwarding:
            return None
        return self.set_interface('ipv6_forwarding', forwarding)

    def set_ipv6_dad_accept(self, dad):
        """Whether to accept DAD (Duplicate Address Detection)"""
        tmp = self.get_interface('ipv6_accept_dad')
        if tmp == dad:
            return None
        return self.set_interface('ipv6_accept_dad', dad)

    def set_ipv6_dad_messages(self, dad):
        """
        The amount of Duplicate Address Detection probes to send.
        Default: 1
        """
        tmp = self.get_interface('ipv6_dad_transmits')
        if tmp == dad:
            return None
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
        tmp = self.get_interface('link_detect')
        if tmp == link_filter:
            return None
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
        tmp = self.get_interface('alias')
        if tmp == ifalias:
            return None
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
        if state == 'up':
            self._admin_state_down_cnt -= 1
            if self._admin_state_down_cnt < 1:
                return self.set_interface('admin_state', state)
        else:
            self._admin_state_down_cnt += 1
            return self.set_interface('admin_state', state)

    def set_path_cost(self, cost):
        """
        Set interface path cost, only relevant for STP enabled interfaces

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_path_cost(4)
        """
        self.set_interface('path_cost', cost)

    def set_path_priority(self, priority):
        """
        Set interface path priority, only relevant for STP enabled interfaces

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_path_priority(4)
        """
        self.set_interface('path_priority', priority)

    def set_port_isolation(self, on_or_off):
        """
        Controls whether a given port will be isolated, which means it will be
        able to communicate with non-isolated ports only. By default this flag
        is off.

        Use enable=1 to enable or enable=0 to disable

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth1').set_port_isolation('on')
        """
        self.set_interface('bridge_port_isolation', on_or_off)

    def set_proxy_arp(self, enable):
        """
        Set per interface proxy ARP configuration

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_proxy_arp(1)
        """
        tmp = self.get_interface('proxy_arp')
        if tmp == enable:
            return None
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
        tmp = self.get_interface('proxy_arp_pvlan')
        if tmp == enable:
            return None
        self.set_interface('proxy_arp_pvlan', enable)

    def get_addr_v4(self):
        """
        Retrieve assigned IPv4 addresses from given interface.
        This is done using the netifaces and ipaddress python modules.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').get_addr_v4()
        ['172.16.33.30/24']
        """
        ipv4 = []
        if AF_INET in ifaddresses(self.config['ifname']):
            for v4_addr in ifaddresses(self.config['ifname'])[AF_INET]:
                # we need to manually assemble a list of IPv4 address/prefix
                prefix = '/' + \
                    str(IPv4Network('0.0.0.0/' + v4_addr['netmask']).prefixlen)
                ipv4.append(v4_addr['addr'] + prefix)
        return ipv4

    def get_addr_v6(self):
        """
        Retrieve assigned IPv6 addresses from given interface.
        This is done using the netifaces and ipaddress python modules.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').get_addr_v6()
        ['fe80::20c:29ff:fe11:a174/64']
        """
        ipv6 = []
        if AF_INET6 in ifaddresses(self.config['ifname']):
            for v6_addr in ifaddresses(self.config['ifname'])[AF_INET6]:
                # Note that currently expanded netmasks are not supported. That means
                # 2001:db00::0/24 is a valid argument while 2001:db00::0/ffff:ff00:: not.
                # see https://docs.python.org/3/library/ipaddress.html
                prefix = '/' + v6_addr['netmask'].split('/')[-1]

                # we alsoneed to remove the interface suffix on link local
                # addresses
                v6_addr['addr'] = v6_addr['addr'].split('%')[0]
                ipv6.append(v6_addr['addr'] + prefix)
        return ipv6

    def get_addr(self):
        """
        Retrieve assigned IPv4 and IPv6 addresses from given interface.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').get_addr()
        ['172.16.33.30/24', 'fe80::20c:29ff:fe11:a174/64']
        """
        return self.get_addr_v4() + self.get_addr_v6()

    def add_addr(self, addr):
        """
        Add IP(v6) address to interface. Address is only added if it is not
        already assigned to that interface. Address format must be validated
        and compressed/normalized before calling this function.

        addr: can be an IPv4 address, IPv6 address, dhcp or dhcpv6!
              IPv4: add IPv4 address to interface
              IPv6: add IPv6 address to interface
              dhcp: start dhclient (IPv4) on interface
              dhcpv6: start WIDE DHCPv6 (IPv6) on interface

        Returns False if address is already assigned and wasn't re-added.
        Example:
        >>> from vyos.ifconfig import Interface
        >>> j = Interface('eth0')
        >>> j.add_addr('192.0.2.1/24')
        >>> j.add_addr('2001:db8::ffff/64')
        >>> j.get_addr()
        ['192.0.2.1/24', '2001:db8::ffff/64']
        """
        # XXX: normalize/compress with ipaddress if calling functions don't?
        # is subnet mask always passed, and in the same way?

        # do not add same address twice
        if addr in self._addr:
            return False

        # get interface network namespace if specified
        netns = self.config.get('netns', None)

        # add to interface
        if addr == 'dhcp':
            self.set_dhcp(True)
        elif addr == 'dhcpv6':
            self.set_dhcpv6(True)
        elif not is_intf_addr_assigned(self.ifname, addr, netns=netns):
            netns_cmd  = f'ip netns exec {netns}' if netns else ''
            tmp = f'{netns_cmd} ip addr add {addr} dev {self.ifname}'
            # Add broadcast address for IPv4
            if is_ipv4(addr): tmp += ' brd +'

            self._cmd(tmp)
        else:
            return False

        # add to cache
        self._addr.append(addr)

        return True

    def del_addr(self, addr):
        """
        Delete IP(v6) address from interface. Address is only deleted if it is
        assigned to that interface. Address format must be exactly the same as
        was used when adding the address.

        addr: can be an IPv4 address, IPv6 address, dhcp or dhcpv6!
              IPv4: delete IPv4 address from interface
              IPv6: delete IPv6 address from interface
              dhcp: stop dhclient (IPv4) on interface
              dhcpv6: stop dhclient (IPv6) on interface

        Returns False if address isn't already assigned and wasn't deleted.
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
        if not addr:
            raise ValueError()

        # get interface network namespace if specified
        netns = self.config.get('netns', None)

        # remove from interface
        if addr == 'dhcp':
            self.set_dhcp(False)
        elif addr == 'dhcpv6':
            self.set_dhcpv6(False)
        elif is_intf_addr_assigned(self.ifname, addr, netns=netns):
            netns_cmd  = f'ip netns exec {netns}' if netns else ''
            self._cmd(f'{netns_cmd} ip addr del {addr} dev {self.ifname}')
        else:
            return False

        # remove from cache
        if addr in self._addr:
            self._addr.remove(addr)

        return True

    def flush_addrs(self):
        """
        Flush all addresses from an interface, including DHCP.

        Will raise an exception on error.
        """
        # stop DHCP(v6) if running
        self.set_dhcp(False)
        self.set_dhcpv6(False)

        netns = get_interface_namespace(self.ifname)
        netns_cmd = f'ip netns exec {netns}' if netns else ''
        cmd = f'{netns_cmd} ip addr flush dev {self.ifname}'
        # flush all addresses
        self._cmd(cmd)

    def add_to_bridge(self, bridge_dict):
        """
        Adds the interface to the bridge with the passed port config.

        Returns False if bridge doesn't exist.
        """

        # drop all interface addresses first
        self.flush_addrs()

        ifname = self.ifname

        for bridge, bridge_config in bridge_dict.items():
            # add interface to bridge - use Section.klass to get BridgeIf class
            Section.klass(bridge)(bridge, create=True).add_port(self.ifname)

            # set bridge port path cost
            if 'cost' in bridge_config:
                self.set_path_cost(bridge_config['cost'])

            # set bridge port path priority
            if 'priority' in bridge_config:
                self.set_path_cost(bridge_config['priority'])

            bridge_vlan_filter = Section.klass(bridge)(bridge, create=True).get_vlan_filter()

            if int(bridge_vlan_filter):
                cur_vlan_ids = get_vlan_ids(ifname)
                add_vlan = []
                native_vlan_id = None
                allowed_vlan_ids= []

                if 'native_vlan' in bridge_config:
                    vlan_id = bridge_config['native_vlan']
                    add_vlan.append(vlan_id)
                    native_vlan_id = vlan_id

                if 'allowed_vlan' in bridge_config:
                    for vlan in bridge_config['allowed_vlan']:
                        vlan_range = vlan.split('-')
                        if len(vlan_range) == 2:
                            for vlan_add in range(int(vlan_range[0]),int(vlan_range[1]) + 1):
                                add_vlan.append(str(vlan_add))
                                allowed_vlan_ids.append(str(vlan_add))
                        else:
                            add_vlan.append(vlan)
                            allowed_vlan_ids.append(vlan)

                # Remove redundant VLANs from the system
                for vlan in list_diff(cur_vlan_ids, add_vlan):
                    cmd = f'bridge vlan del dev {ifname} vid {vlan} master'
                    self._cmd(cmd)

                for vlan in allowed_vlan_ids:
                    cmd = f'bridge vlan add dev {ifname} vid {vlan} master'
                    self._cmd(cmd)
                # Setting native VLAN to system
                if native_vlan_id:
                    cmd = f'bridge vlan add dev {ifname} vid {native_vlan_id} pvid untagged master'
                    self._cmd(cmd)

    def set_dhcp(self, enable):
        """
        Enable/Disable DHCP client on a given interface.
        """
        if enable not in [True, False]:
            raise ValueError()

        ifname = self.ifname
        config_base = directories['isc_dhclient_dir'] + '/dhclient'
        dhclient_config_file = f'{config_base}_{ifname}.conf'
        dhclient_lease_file = f'{config_base}_{ifname}.leases'
        systemd_override_file = f'/run/systemd/system/dhclient@{ifname}.service.d/10-override.conf'
        systemd_service = f'dhclient@{ifname}.service'

        # Rendered client configuration files require the apsolute config path
        self.config['isc_dhclient_dir'] = directories['isc_dhclient_dir']

        # 'up' check is mandatory b/c even if the interface is A/D, as soon as
        # the DHCP client is started the interface will be placed in u/u state.
        # This is not what we intended to do when disabling an interface.
        if enable and 'disable' not in self.config:
            if dict_search('dhcp_options.host_name', self.config) == None:
                # read configured system hostname.
                # maybe change to vyos-hostsd client ???
                hostname = 'vyos'
                hostname_file = '/etc/hostname'
                if os.path.isfile(hostname_file):
                    hostname = read_file(hostname_file)
                tmp = {'dhcp_options' : { 'host_name' : hostname}}
                self.config = dict_merge(tmp, self.config)

            render(systemd_override_file, 'dhcp-client/override.conf.j2', self.config)
            render(dhclient_config_file, 'dhcp-client/ipv4.j2', self.config)

            # Reload systemd unit definitons as some options are dynamically generated
            self._cmd('systemctl daemon-reload')

            # When the DHCP client is restarted a brief outage will occur, as
            # the old lease is released a new one is acquired (T4203). We will
            # only restart DHCP client if it's option changed, or if it's not
            # running, but it should be running (e.g. on system startup)
            if 'dhcp_options_changed' in self.config or not is_systemd_service_active(systemd_service):
                return self._cmd(f'systemctl restart {systemd_service}')
        else:
            if is_systemd_service_active(systemd_service):
                self._cmd(f'systemctl stop {systemd_service}')
            # cleanup old config files
            for file in [dhclient_config_file, systemd_override_file, dhclient_lease_file]:
                if os.path.isfile(file):
                    os.remove(file)

        return None

    def set_dhcpv6(self, enable):
        """
        Enable/Disable DHCPv6 client on a given interface.
        """
        if enable not in [True, False]:
            raise ValueError()

        ifname = self.ifname
        config_base = directories['dhcp6_client_dir']
        config_file = f'{config_base}/dhcp6c.{ifname}.conf'
        script_file = f'/etc/wide-dhcpv6/dhcp6c.{ifname}.script' # can not live under /run b/c of noexec mount option
        systemd_override_file = f'/run/systemd/system/dhcp6c@{ifname}.service.d/10-override.conf'
        systemd_service = f'dhcp6c@{ifname}.service'

        # Rendered client configuration files require additional settings
        config = deepcopy(self.config)
        config['dhcp6_client_dir'] = directories['dhcp6_client_dir']
        config['dhcp6_script_file'] = script_file

        if enable and 'disable' not in config:
            render(systemd_override_file, 'dhcp-client/ipv6.override.conf.j2', config)
            render(config_file, 'dhcp-client/ipv6.j2', config)
            render(script_file, 'dhcp-client/dhcp6c-script.j2', config, permission=0o755)

            # Reload systemd unit definitons as some options are dynamically generated
            self._cmd('systemctl daemon-reload')

            # We must ignore any return codes. This is required to enable
            # DHCPv6-PD for interfaces which are yet not up and running.
            return self._popen(f'systemctl restart {systemd_service}')
        else:
            if is_systemd_service_active(systemd_service):
                self._cmd(f'systemctl stop {systemd_service}')
            if os.path.isfile(config_file):
                os.remove(config_file)
            if os.path.isfile(script_file):
                os.remove(script_file)

        return None

    def set_mirror_redirect(self):
        # Please refer to the document for details
        #   - https://man7.org/linux/man-pages/man8/tc.8.html
        #   - https://man7.org/linux/man-pages/man8/tc-mirred.8.html
        # Depening if we are the source or the target interface of the port
        # mirror we need to setup some variables.

        # Don't allow for netns yet
        if 'netns' in self.config:
            return None

        source_if = self.config['ifname']

        mirror_config = None
        if 'mirror' in self.config:
            mirror_config = self.config['mirror']
        if 'is_mirror_intf' in self.config:
            source_if = next(iter(self.config['is_mirror_intf']))
            mirror_config = self.config['is_mirror_intf'][source_if].get('mirror', None)

        redirect_config = None

        # clear existing ingess - ignore errors (e.g. "Error: Cannot find specified
        # qdisc on specified device") - we simply cleanup all stuff here
        if not 'traffic_policy' in self.config:
            self._popen(f'tc qdisc del dev {source_if} parent ffff: 2>/dev/null');
            self._popen(f'tc qdisc del dev {source_if} parent 1: 2>/dev/null');

        # Apply interface mirror policy
        if mirror_config:
            for direction, target_if in mirror_config.items():
                if direction == 'ingress':
                    handle = 'ffff: ingress'
                    parent = 'ffff:'
                elif direction == 'egress':
                    handle = '1: root prio'
                    parent = '1:'

                # Mirror egress traffic
                mirror_cmd  = f'tc qdisc add dev {source_if} handle {handle}; '
                # Export the mirrored traffic to the interface
                mirror_cmd += f'tc filter add dev {source_if} parent {parent} protocol '\
                              f'all prio 10 u32 match u32 0 0 flowid 1:1 action mirred '\
                              f'egress mirror dev {target_if}'
                _, err = self._popen(mirror_cmd)
                if err: print('tc qdisc(filter for mirror port failed')

        # Apply interface traffic redirection policy
        elif 'redirect' in self.config:
            _, err = self._popen(f'tc qdisc add dev {source_if} handle ffff: ingress')
            if err: print(f'tc qdisc add for redirect failed!')

            target_if = self.config['redirect']
            _, err = self._popen(f'tc filter add dev {source_if} parent ffff: protocol '\
                                 f'all prio 10 u32 match u32 0 0 flowid 1:1 action mirred '\
                                 f'egress redirect dev {target_if}')
            if err: print('tc filter add for redirect failed')

    def set_per_client_thread(self, enable):
        """
        Per-device control to enable/disable the threaded mode for all the napi
        instances of the given network device, without the need for a device up/down.

        User sets it to 1 or 0 to enable or disable threaded mode.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('wg1').set_per_client_thread(1)
        """
        # In the case of a "virtual" interface like wireguard, the sysfs
        # node is only created once there is a peer configured. We can now
        # add a verify() code-path for this or make this dynamic without
        # nagging the user
        tmp = self._sysfs_get['per_client_thread']['location']
        if not os.path.exists(tmp):
            return None

        tmp = self.get_interface('per_client_thread')
        if tmp == enable:
            return None
        self.set_interface('per_client_thread', enable)

    def set_eapol(self) -> None:
        """ Take care about EAPoL supplicant daemon """

        # XXX: wpa_supplicant works on the source interface
        cfg_dir = '/run/wpa_supplicant'
        wpa_supplicant_conf = f'{cfg_dir}/{self.ifname}.conf'
        eapol_action='stop'

        if 'eapol' in self.config:
            # The default is a fallback to hw_id which is not present for any interface
            # other then an ethernet interface. Thus we emulate hw_id by reading back the
            # Kernel assigned MAC address
            if 'hw_id' not in self.config:
                self.config['hw_id'] = read_file(f'/sys/class/net/{self.ifname}/address')
            render(wpa_supplicant_conf, 'ethernet/wpa_supplicant.conf.j2', self.config)

            cert_file_path = os.path.join(cfg_dir, f'{self.ifname}_cert.pem')
            cert_key_path = os.path.join(cfg_dir, f'{self.ifname}_cert.key')

            cert_name = self.config['eapol']['certificate']
            pki_cert = self.config['pki']['certificate'][cert_name]

            loaded_pki_cert = load_certificate(pki_cert['certificate'])
            loaded_ca_certs = {load_certificate(c['certificate'])
                for c in self.config['pki']['ca'].values()} if 'ca' in self.config['pki'] else {}

            cert_full_chain = find_chain(loaded_pki_cert, loaded_ca_certs)

            write_file(cert_file_path,
                    '\n'.join(encode_certificate(c) for c in cert_full_chain))
            write_file(cert_key_path, wrap_private_key(pki_cert['private']['key']))

            if 'ca_certificate' in self.config['eapol']:
                ca_cert_file_path = os.path.join(cfg_dir, f'{self.ifname}_ca.pem')
                ca_chains = []

                for ca_cert_name in self.config['eapol']['ca_certificate']:
                    pki_ca_cert = self.config['pki']['ca'][ca_cert_name]
                    loaded_ca_cert = load_certificate(pki_ca_cert['certificate'])
                    ca_full_chain = find_chain(loaded_ca_cert, loaded_ca_certs)
                    ca_chains.append(
                        '\n'.join(encode_certificate(c) for c in ca_full_chain))

                write_file(ca_cert_file_path, '\n'.join(ca_chains))

            eapol_action='reload-or-restart'

        # start/stop WPA supplicant service
        self._cmd(f'systemctl {eapol_action} wpa_supplicant-wired@{self.ifname}')

        if 'eapol' not in self.config:
            # delete configuration on interface removal
            if os.path.isfile(wpa_supplicant_conf):
                os.unlink(wpa_supplicant_conf)

    def update(self, config):
        """ General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface. """

        if self.debug:
            import pprint
            pprint.pprint(config)

        # Cache the configuration - it will be reused inside e.g. DHCP handler
        # XXX: maybe pass the option via __init__ in the future and rename this
        # method to apply()?
        self.config = config

        # Change interface MAC address - re-set to real hardware address (hw-id)
        # if custom mac is removed. Skip if bond member.
        if 'is_bond_member' not in config:
            mac = config.get('hw_id')
            if 'mac' in config:
                mac = config.get('mac')
            if mac:
                self.set_mac(mac)

        # If interface is connected to NETNS we don't have to check all other
        # settings like MTU/IPv6/sysctl values, etc.
        # Since the interface is pushed onto a separate logical stack
        # Configure NETNS
        if dict_search('netns', config) != None:
            if not is_netns_interface(self.ifname, self.config['netns']):
                self.set_netns(config.get('netns', ''))
        else:
            self.del_netns(config.get('netns', ''))

        # Update interface description
        self.set_alias(config.get('description', ''))

        # Ignore link state changes
        value = '2' if 'disable_link_detect' in config else '1'
        self.set_link_detect(value)

        # Configure assigned interface IP addresses. No longer
        # configured addresses will be removed first
        new_addr = config.get('address', [])

        # always ensure DHCP client is stopped (when not configured explicitly)
        if 'dhcp' not in new_addr:
            self.del_addr('dhcp')

        # always ensure DHCPv6 client is stopped (when not configured as client
        # for IPv6 address or prefix delegation)
        dhcpv6pd = dict_search('dhcpv6_options.pd', config)
        dhcpv6pd = dhcpv6pd != None and len(dhcpv6pd) != 0
        if 'dhcpv6' not in new_addr and not dhcpv6pd:
            self.del_addr('dhcpv6')

        # determine IP addresses which are assigned to the interface and build a
        # list of addresses which are no longer in the dict so they can be removed
        if 'address_old' in config:
            for addr in list_diff(config['address_old'], new_addr):
                # we will delete all interface specific IP addresses if they are not
                # explicitly configured on the CLI
                if is_ipv6_link_local(addr):
                    eui64 = mac2eui64(self.get_mac(), link_local_prefix)
                    if addr != f'{eui64}/64':
                        self.del_addr(addr)
                else:
                    self.del_addr(addr)

        # start DHCPv6 client when only PD was configured
        if dhcpv6pd:
            self.set_dhcpv6(True)

        # XXX: Bind interface to given VRF or unbind it if vrf is not set. Unbinding
        # will call 'ip link set dev eth0 nomaster' which will also drop the
        # interface out of any bridge or bond - thus this is checked before.
        if 'is_bond_member' in config:
            bond_if = next(iter(config['is_bond_member']))
            tmp = get_interface_config(config['ifname'])
            if 'master' in tmp and tmp['master'] != bond_if:
                self.set_vrf('')

        elif 'is_bridge_member' in config:
            bridge_if = next(iter(config['is_bridge_member']))
            tmp = get_interface_config(config['ifname'])
            if 'master' in tmp and tmp['master'] != bridge_if:
                self.set_vrf('')
        else:
            self.set_vrf(config.get('vrf', ''))

        # Add this section after vrf T4331
        for addr in new_addr:
            self.add_addr(addr)

        # Configure MSS value for IPv4 TCP connections
        tmp = dict_search('ip.adjust_mss', config)
        value = tmp if (tmp != None) else '0'
        self.set_tcp_ipv4_mss(value)

        # Configure ARP cache timeout in milliseconds - has default value
        tmp = dict_search('ip.arp_cache_timeout', config)
        value = tmp if (tmp != None) else '30'
        self.set_arp_cache_tmo(value)

        # Configure ARP filter configuration
        tmp = dict_search('ip.disable_arp_filter', config)
        value = '0' if (tmp != None) else '1'
        self.set_arp_filter(value)

        # Configure ARP accept
        tmp = dict_search('ip.enable_arp_accept', config)
        value = '1' if (tmp != None) else '0'
        self.set_arp_accept(value)

        # Configure ARP announce
        tmp = dict_search('ip.enable_arp_announce', config)
        value = '1' if (tmp != None) else '0'
        self.set_arp_announce(value)

        # Configure ARP ignore
        tmp = dict_search('ip.enable_arp_ignore', config)
        value = '1' if (tmp != None) else '0'
        self.set_arp_ignore(value)

        # Enable proxy-arp on this interface
        tmp = dict_search('ip.enable_proxy_arp', config)
        value = '1' if (tmp != None) else '0'
        self.set_proxy_arp(value)

        # Enable private VLAN proxy ARP on this interface
        tmp = dict_search('ip.proxy_arp_pvlan', config)
        value = '1' if (tmp != None) else '0'
        self.set_proxy_arp_pvlan(value)

        # IPv4 forwarding
        tmp = dict_search('ip.disable_forwarding', config)
        value = '0' if (tmp != None) else '1'
        self.set_ipv4_forwarding(value)

        # IPv4 directed broadcast forwarding
        tmp = dict_search('ip.enable_directed_broadcast', config)
        value = '1' if (tmp != None) else '0'
        self.set_ipv4_directed_broadcast(value)

        # IPv4 source-validation
        tmp = dict_search('ip.source_validation', config)
        value = tmp if (tmp != None) else '0'
        self.set_ipv4_source_validation(value)

        # IPv6 source-validation
        tmp = dict_search('ipv6.source_validation', config)
        value = tmp if (tmp != None) else '0'
        self.set_ipv6_source_validation(value)

        # MTU - Maximum Transfer Unit has a default value. It must ALWAYS be set
        # before mangling any IPv6 option. If MTU is less then 1280 IPv6 will be
        # automatically disabled by the kernel. Also MTU must be increased before
        # configuring any IPv6 address on the interface.
        if 'mtu' in config and dict_search('dhcp_options.mtu', config) == None:
            self.set_mtu(config.get('mtu'))

        # Configure MSS value for IPv6 TCP connections
        tmp = dict_search('ipv6.adjust_mss', config)
        value = tmp if (tmp != None) else '0'
        self.set_tcp_ipv6_mss(value)

        # IPv6 forwarding
        tmp = dict_search('ipv6.disable_forwarding', config)
        value = '0' if (tmp != None) else '1'
        self.set_ipv6_forwarding(value)

        # IPv6 router advertisements
        tmp = dict_search('ipv6.address.autoconf', config)
        value = '2' if (tmp != None) else '1'
        if 'dhcpv6' in new_addr:
            value = '2'
        self.set_ipv6_accept_ra(value)

        # IPv6 address autoconfiguration
        tmp = dict_search('ipv6.address.autoconf', config)
        value = '1' if (tmp != None) else '0'
        self.set_ipv6_autoconf(value)

        # Whether to accept IPv6 DAD (Duplicate Address Detection) packets
        tmp = dict_search('ipv6.accept_dad', config)
        # Not all interface types got this CLI option, but if they do, there
        # is an XML defaultValue available
        if (tmp != None): self.set_ipv6_dad_accept(tmp)

        # IPv6 DAD tries
        tmp = dict_search('ipv6.dup_addr_detect_transmits', config)
        # Not all interface types got this CLI option, but if they do, there
        # is an XML defaultValue available
        if (tmp != None): self.set_ipv6_dad_messages(tmp)

        # Delete old IPv6 EUI64 addresses before changing MAC
        for addr in (dict_search('ipv6.address.eui64_old', config) or []):
            self.del_ipv6_eui64_address(addr)

        # Manage IPv6 link-local addresses
        if dict_search('ipv6.address.no_default_link_local', config) != None:
            self.del_ipv6_eui64_address(link_local_prefix)
        else:
            self.add_ipv6_eui64_address(link_local_prefix)

        # Add IPv6 EUI-based addresses
        tmp = dict_search('ipv6.address.eui64', config)
        if tmp:
            for addr in tmp:
                self.add_ipv6_eui64_address(addr)

        # Configure IPv6 base time in milliseconds - has default value
        tmp = dict_search('ipv6.base_reachable_time', config)
        value = tmp if (tmp != None) else '30'
        self.set_ipv6_cache_tmo(value)

        # re-add ourselves to any bridge we might have fallen out of
        if 'is_bridge_member' in config:
            tmp = config.get('is_bridge_member')
            self.add_to_bridge(tmp)

        # configure interface mirror or redirection target
        self.set_mirror_redirect()

        # enable/disable NAPI threading mode
        tmp = dict_search('per_client_thread', config)
        value = '1' if (tmp != None) else '0'
        self.set_per_client_thread(value)

        # Enable/Disable of an interface must always be done at the end of the
        # derived class to make use of the ref-counting set_admin_state()
        # function. We will only enable the interface if 'up' was called as
        # often as 'down'. This is required by some interface implementations
        # as certain parameters can only be changed when the interface is
        # in admin-down state. This ensures the link does not flap during
        # reconfiguration.
        state = 'down' if 'disable' in config else 'up'
        self.set_admin_state(state)

        # remove no longer required 802.1ad (Q-in-Q VLANs)
        ifname = config['ifname']
        for vif_s_id in config.get('vif_s_remove', {}):
            vif_s_ifname = f'{ifname}.{vif_s_id}'
            VLANIf(vif_s_ifname).remove()

        # create/update 802.1ad (Q-in-Q VLANs)
        for vif_s_id, vif_s_config in config.get('vif_s', {}).items():
            tmp = deepcopy(VLANIf.get_config())
            tmp['protocol'] = vif_s_config['protocol']
            tmp['source_interface'] = ifname
            tmp['vlan_id'] = vif_s_id

            # It is not possible to change the VLAN encapsulation protocol
            # "on-the-fly". For this "quirk" we need to actively delete and
            # re-create the VIF-S interface.
            vif_s_ifname = f'{ifname}.{vif_s_id}'
            if self.exists(vif_s_ifname):
                cur_cfg = get_interface_config(vif_s_ifname)
                protocol = dict_search('linkinfo.info_data.protocol', cur_cfg).lower()
                if protocol != vif_s_config['protocol']:
                    VLANIf(vif_s_ifname).remove()

            s_vlan = VLANIf(vif_s_ifname, **tmp)
            s_vlan.update(vif_s_config)

            # remove no longer required client VLAN (vif-c)
            for vif_c_id in vif_s_config.get('vif_c_remove', {}):
                vif_c_ifname = f'{vif_s_ifname}.{vif_c_id}'
                VLANIf(vif_c_ifname).remove()

            # create/update client VLAN (vif-c) interface
            for vif_c_id, vif_c_config in vif_s_config.get('vif_c', {}).items():
                tmp = deepcopy(VLANIf.get_config())
                tmp['source_interface'] = vif_s_ifname
                tmp['vlan_id'] = vif_c_id

                vif_c_ifname = f'{vif_s_ifname}.{vif_c_id}'
                c_vlan = VLANIf(vif_c_ifname, **tmp)
                c_vlan.update(vif_c_config)

        # remove no longer required 802.1q VLAN interfaces
        for vif_id in config.get('vif_remove', {}):
            vif_ifname = f'{ifname}.{vif_id}'
            VLANIf(vif_ifname).remove()

        # create/update 802.1q VLAN interfaces
        for vif_id, vif_config in config.get('vif', {}).items():
            vif_ifname = f'{ifname}.{vif_id}'
            tmp = deepcopy(VLANIf.get_config())
            tmp['source_interface'] = ifname
            tmp['vlan_id'] = vif_id

            # We need to ensure that the string format is consistent, and we need to exclude redundant spaces.
            sep = ' '
            if 'egress_qos' in vif_config:
                # Unwrap strings into arrays
                egress_qos_array = vif_config['egress_qos'].split()
                # The split array is spliced according to the fixed format
                tmp['egress_qos'] = sep.join(egress_qos_array)

            if 'ingress_qos' in vif_config:
                # Unwrap strings into arrays
                ingress_qos_array = vif_config['ingress_qos'].split()
                # The split array is spliced according to the fixed format
                tmp['ingress_qos'] = sep.join(ingress_qos_array)

            # Since setting the QoS control parameters in the later stage will
            # not completely delete the old settings,
            # we still need to delete the VLAN encapsulation interface in order to
            # ensure that the changed settings are effective.
            cur_cfg = get_interface_config(vif_ifname)
            qos_str = ''
            tmp2 = dict_search('linkinfo.info_data.ingress_qos', cur_cfg)
            if 'ingress_qos' in tmp and tmp2:
                for item in tmp2:
                    from_key = item['from']
                    to_key = item['to']
                    qos_str += f'{from_key}:{to_key} '
                if qos_str != tmp['ingress_qos']:
                    if self.exists(vif_ifname):
                        VLANIf(vif_ifname).remove()

            qos_str = ''
            tmp2 = dict_search('linkinfo.info_data.egress_qos', cur_cfg)
            if 'egress_qos' in tmp and tmp2:
                for item in tmp2:
                    from_key = item['from']
                    to_key = item['to']
                    qos_str += f'{from_key}:{to_key} '
                if qos_str != tmp['egress_qos']:
                    if self.exists(vif_ifname):
                        VLANIf(vif_ifname).remove()

            vlan = VLANIf(vif_ifname, **tmp)
            vlan.update(vif_config)


class VLANIf(Interface):
    """ Specific class which abstracts 802.1q and 802.1ad (Q-in-Q) VLAN interfaces """
    iftype = 'vlan'

    def _create(self):
        # bail out early if interface already exists
        if self.exists(f'{self.ifname}'):
            return

        # If source_interface or vlan_id was not explicitly defined (e.g. when
        # calling  VLANIf('eth0.1').remove() we can define source_interface and
        # vlan_id here, as it's quiet obvious that it would be eth0 in that case.
        if 'source_interface' not in self.config:
            self.config['source_interface'] = '.'.join(self.ifname.split('.')[:-1])
        if 'vlan_id' not in self.config:
            self.config['vlan_id'] = self.ifname.split('.')[-1]

        cmd = 'ip link add link {source_interface} name {ifname} type vlan id {vlan_id}'
        if 'protocol' in self.config:
            cmd += ' protocol {protocol}'
        if 'ingress_qos' in self.config:
            cmd += ' ingress-qos-map {ingress_qos}'
        if 'egress_qos' in self.config:
            cmd += ' egress-qos-map {egress_qos}'

        self._cmd(cmd.format(**self.config))

        # interface is always A/D down. It needs to be enabled explicitly
        self.set_admin_state('down')

    def set_admin_state(self, state):
        """
        Set interface administrative state to be 'up' or 'down'

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0.10').set_admin_state('down')
        >>> Interface('eth0.10').get_admin_state()
        'down'
        """
        # A VLAN interface can only be placed in admin up state when
        # the lower interface is up, too
        lower_interface = glob(f'/sys/class/net/{self.ifname}/lower*/flags')[0]
        with open(lower_interface, 'r') as f:
            flags = f.read()
        # If parent is not up - bail out as we can not bring up the VLAN.
        # Flags are defined in kernel source include/uapi/linux/if.h
        if not int(flags, 16) & 1:
            return None

        return super().set_admin_state(state)
