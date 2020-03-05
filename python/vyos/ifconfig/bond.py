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

from vyos.ifconfig.interface import Interface
from vyos.ifconfig.vlan import VLANIf

from vyos.validate import *


class BondIf(VLANIf):
    """
    The Linux bonding driver provides a method for aggregating multiple network
    interfaces into a single logical "bonded" interface. The behavior of the
    bonded interfaces depends upon the mode; generally speaking, modes provide
    either hot standby or load balancing services. Additionally, link integrity
    monitoring may be performed.
    """

    _sysfs_set = {**VLANIf._sysfs_set, **{
        'bond_hash_policy': {
            'validate': lambda v: assert_list(v, ['layer2', 'layer2+3', 'layer3+4', 'encap2+3', 'encap3+4']),
            'location': '/sys/class/net/{ifname}/bonding/xmit_hash_policy',
        },
        'bond_miimon': {
            'validate': assert_positive,
            'location': '/sys/class/net/{ifname}/bonding/miimon'
        },
        'bond_arp_interval': {
            'validate': assert_positive,
            'location': '/sys/class/net/{ifname}/bonding/arp_interval'
        },
        'bond_arp_ip_target': {
            # XXX: no validation of the IP
            'location': '/sys/class/net/{ifname}/bonding/arp_ip_target',
        },
        'bond_add_port': {
            'location': '/sys/class/net/{ifname}+{value}/bonding/slaves',
        },
        'bond_del_port': {
            'location': '/sys/class/net/{ifname}-{value}/bonding/slaves',
        },
        'bond_primary': {
            'convert': lambda name: name if name else '\0',
            'location': '/sys/class/net/{ifname}/bonding/primary',
        },
        'bond_mode': {
            'validate': lambda v: assert_list(v, ['balance-rr', 'active-backup', 'balance-xor', 'broadcast', '802.3ad', 'balance-tlb', 'balance-alb']),
            'location': '/sys/class/net/{ifname}/bonding/mode',
        },
    }}

    _sysfs_get = {**VLANIf._sysfs_get, **{
        'bond_arp_ip_target': {
            'location': '/sys/class/net/{ifname}/bonding/arp_ip_target',
        }
    }}

    default = {
        'type': 'bond',
    }

    def __init__(self, ifname, **kargs):
        super().__init__(ifname, **kargs)

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
        # when a bond member gets deleted, all members are placed in A/D state
        # even when they are enabled inside CLI. This will make the config
        # and system look async.
        slave_list = []
        for s in self.get_slaves():
            slave = {
                'ifname': s,
                'state': Interface(s).get_state()
            }
            slave_list.append(slave)

        # remove bond master which places members in disabled state
        super().remove()

        # replicate previous interface state before bond destruction back to
        # physical interface
        for slave in slave_list:
             i = Interface(slave['ifname'])
             i.set_state(slave['state'])

    def set_hash_policy(self, mode):
        """
        Selects the transmit hash policy to use for slave selection in
        balance-xor, 802.3ad, and tlb modes. Possible values are: layer2,
        layer2+3, layer3+4, encap2+3, encap3+4.

        The default value is layer2

        Example:
        >>> from vyos.ifconfig import BondIf
        >>> BondIf('bond0').set_hash_policy('layer2+3')
        """
        self.set_interface('bond_hash_policy', mode)

    def set_arp_interval(self, interval):
        """
        Specifies the ARP link monitoring frequency in milliseconds.

        The ARP monitor works by periodically checking the slave devices
        to determine whether they have sent or received traffic recently
        (the precise criteria depends upon the bonding mode, and the
        state of the slave). Regular traffic is generated via ARP probes
        issued for the addresses specified by the arp_ip_target option.

        If ARP monitoring is used in an etherchannel compatible mode
        (modes 0 and 2), the switch should be configured in a mode that
        evenly distributes packets across all links. If the switch is
        configured to distribute the packets in an XOR fashion, all
        replies from the ARP targets will be received on the same link
        which could cause the other team members to fail.

        value of 0 disables ARP monitoring. The default value is 0.

        Example:
        >>> from vyos.ifconfig import BondIf
        >>> BondIf('bond0').set_arp_interval('100')
        """
        if int(interval) == 0:
            """
            Specifies the MII link monitoring frequency in milliseconds.
            This determines how often the link state of each slave is
            inspected for link failures. A value of zero disables MII
            link monitoring. A value of 100 is a good starting point.
            """
            return self.set_interface('bond_miimon', interval)
        else:
            return self.set_interface('bond_arp_interval', interval)

    def get_arp_ip_target(self):
        """
        Specifies the IP addresses to use as ARP monitoring peers when
        arp_interval is > 0. These are the targets of the ARP request sent to
        determine the health of the link to the targets. Specify these values
        in ddd.ddd.ddd.ddd format. Multiple IP addresses must be separated by
        a comma. At least one IP address must be given for ARP monitoring to
        function. The maximum number of targets that can be specified is 16.

        The default value is no IP addresses.

        Example:
        >>> from vyos.ifconfig import BondIf
        >>> BondIf('bond0').get_arp_ip_target()
        '192.0.2.1'
        """
        return self.get_interface('bond_arp_ip_target')

    def set_arp_ip_target(self, target):
        """
        Specifies the IP addresses to use as ARP monitoring peers when
        arp_interval is > 0. These are the targets of the ARP request sent to
        determine the health of the link to the targets. Specify these values
        in ddd.ddd.ddd.ddd format. Multiple IP addresses must be separated by
        a comma. At least one IP address must be given for ARP monitoring to
        function. The maximum number of targets that can be specified is 16.

        The default value is no IP addresses.

        Example:
        >>> from vyos.ifconfig import BondIf
        >>> BondIf('bond0').set_arp_ip_target('192.0.2.1')
        >>> BondIf('bond0').get_arp_ip_target()
        '192.0.2.1'
        """
        return self.set_interface('bond_arp_ip_target', target)

    def add_port(self, interface):
        """
        Enslave physical interface to bond.

        Example:
        >>> from vyos.ifconfig import BondIf
        >>> BondIf('bond0').add_port('eth0')
        >>> BondIf('bond0').add_port('eth1')
        """
        # An interface can only be added to a bond if it is in 'down' state. If
        # interface is in 'up' state, the following Kernel error will  be thrown:
        # bond0: eth1 is up - this may be due to an out of date ifenslave.
        Interface(interface).set_state('down')
        return self.set_interface('bond_add_port', interface)

    def del_port(self, interface):
        """
        Remove physical port from bond

        Example:
        >>> from vyos.ifconfig import BondIf
        >>> BondIf('bond0').del_port('eth1')
        """
        return self.set_interface('bond_del_port', interface)

    def get_slaves(self):
        """
        Return a list with all configured slave interfaces on this bond.

        Example:
        >>> from vyos.ifconfig import BondIf
        >>> BondIf('bond0').get_slaves()
        ['eth1', 'eth2']
        """
        enslaved_ifs = []
        # retrieve real enslaved interfaces from OS kernel
        sysfs_bond = '/sys/class/net/{}'.format(self.config['ifname'])
        if os.path.isdir(sysfs_bond):
            for directory in os.listdir(sysfs_bond):
                if 'lower_' in directory:
                    enslaved_ifs.append(directory.replace('lower_', ''))

        return enslaved_ifs

    def set_primary(self, interface):
        """
        A string (eth0, eth2, etc) specifying which slave is the primary
        device. The specified device will always be the active slave while it
        is available. Only when the primary is off-line will alternate devices
        be used. This is useful when one slave is preferred over another, e.g.,
        when one slave has higher throughput than another.

        The primary option is only valid for active-backup, balance-tlb and
        balance-alb mode.

        Example:
        >>> from vyos.ifconfig import BondIf
        >>> BondIf('bond0').set_primary('eth2')
        """
        return self.set_interface('bond_primary', interface)

    def set_mode(self, mode):
        """
        Specifies one of the bonding policies. The default is balance-rr
        (round robin).

        Possible values are: balance-rr, active-backup, balance-xor,
        broadcast, 802.3ad, balance-tlb, balance-alb

        NOTE: the bonding mode can not be changed when the bond itself has
        slaves

        Example:
        >>> from vyos.ifconfig import BondIf
        >>> BondIf('bond0').set_mode('802.3ad')
        """
        return self.set_interface('bond_mode', mode)
