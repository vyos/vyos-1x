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

from vyos.ifconfig.interface import Interface
from vyos.utils.dict import dict_search
from vyos.utils.assertion import assert_list
from vyos.utils.assertion import assert_mac
from vyos.utils.assertion import assert_positive

@Interface.register
class BondIf(Interface):
    """
    The Linux bonding driver provides a method for aggregating multiple network
    interfaces into a single logical "bonded" interface. The behavior of the
    bonded interfaces depends upon the mode; generally speaking, modes provide
    either hot standby or load balancing services. Additionally, link integrity
    monitoring may be performed.
    """

    iftype = 'bond'
    definition = {
        **Interface.definition,
        ** {
            'section': 'bonding',
            'prefixes': ['bond', ],
            'broadcast': True,
            'bridgeable': True,
        },
    }

    _sysfs_set = {**Interface._sysfs_set, **{
        'bond_hash_policy': {
            'validate': lambda v: assert_list(v, ['layer2', 'layer2+3', 'layer3+4', 'encap2+3', 'encap3+4']),
            'location': '/sys/class/net/{ifname}/bonding/xmit_hash_policy',
        },
        'bond_min_links': {
            'validate': assert_positive,
            'location': '/sys/class/net/{ifname}/bonding/min_links',
        },
        'bond_lacp_rate': {
            'validate': lambda v: assert_list(v, ['slow', 'fast']),
            'location': '/sys/class/net/{ifname}/bonding/lacp_rate',
        },
        'bond_system_mac': {
            'validate': lambda v: assert_mac(v, test_all_zero=False),
            'location': '/sys/class/net/{ifname}/bonding/ad_actor_system',
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
            'location': '/sys/class/net/{ifname}/bonding/slaves',
        },
        'bond_del_port': {
            'location': '/sys/class/net/{ifname}/bonding/slaves',
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

    _sysfs_get = {**Interface._sysfs_get, **{
        'bond_arp_ip_target': {
            'location': '/sys/class/net/{ifname}/bonding/arp_ip_target',
        },
        'bond_mode': {
            'location': '/sys/class/net/{ifname}/bonding/mode',
        }
    }}

    @staticmethod
    def get_inherit_bond_options() -> list:
        """
        Returns list of option
        which are inherited from bond interface to member interfaces
        :return: List of interface options
        :rtype: list
        """
        options = [
            'mtu'
        ]
        return options

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
                'state': Interface(s).get_admin_state()
            }
            slave_list.append(slave)

        # remove bond master which places members in disabled state
        super().remove()

        # replicate previous interface state before bond destruction back to
        # physical interface
        for slave in slave_list:
             i = Interface(slave['ifname'])
             i.set_admin_state(slave['state'])

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

    def set_min_links(self, number):
        """
        Specifies the minimum number of links that must be active before
	    asserting carrier. It is similar to the Cisco EtherChannel min-links
	    feature. This allows setting the minimum number of member ports that
	    must be up (link-up state) before marking the bond device as up
	    (carrier on). This is useful for situations where higher level services
	    such as clustering want to ensure a minimum number of low bandwidth
	    links are active before switchover. This option only affect 802.3ad
	    mode.

	    The default value is 0. This will cause carrier to be asserted (for
	    802.3ad mode) whenever there is an active aggregator, regardless of the
	    number of available links in that aggregator. Note that, because an
	    aggregator cannot be active without at least one available link,
	    setting this option to 0 or to 1 has the exact same effect.

        Example:
        >>> from vyos.ifconfig import BondIf
        >>> BondIf('bond0').set_min_links('0')
        """
        self.set_interface('bond_min_links', number)

    def set_lacp_rate(self, slow_fast):
        """
        Option specifying the rate in which we'll ask our link partner
	    to transmit LACPDU packets in 802.3ad mode.  Possible values
	    are:

	    slow or 0
		    Request partner to transmit LACPDUs every 30 seconds

	    fast or 1
		    Request partner to transmit LACPDUs every 1 second

	    The default is slow.

        Example:
        >>> from vyos.ifconfig import BondIf
        >>> BondIf('bond0').set_lacp_rate('slow')
        """
        self.set_interface('bond_lacp_rate', slow_fast)

    def set_miimon_interval(self, interval):
        """
        Specifies the MII link monitoring frequency in milliseconds. This
        determines how often the link state of each slave is inspected for link
        failures. A value of zero disables MII link monitoring. A value of 100
        is a good starting point.

        The default value is 0.

        Example:
        >>> from vyos.ifconfig import BondIf
        >>> BondIf('bond0').set_miimon_interval('100')
        """
        return self.set_interface('bond_miimon', interval)

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
        # As this function might also be called from update() of a VLAN interface
        # we must check if the bond_arp_ip_target retrieval worked or not - as this
        # can not be set for a bond vif interface
        try:
            return self.get_interface('bond_arp_ip_target')
        except FileNotFoundError:
            return ''

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

        # From drivers/net/bonding/bond_main.c:
        # ...
        # bond_set_slave_link_state(new_slave,
        #      BOND_LINK_UP,
        #      BOND_SLAVE_NOTIFY_NOW);
        # ...
        #
        # The kernel will ALWAYS place new bond members in "up" state regardless
        # what the CLI will tell us!

        # Physical interface must be in admin down state before they can be
        # enslaved. If this is not the case an error will be shown:
        # bond0: eth0 is up - this may be due to an out of date ifenslave
        slave = Interface(interface)
        slave_state = slave.get_admin_state()
        if slave_state == 'up':
            slave.set_admin_state('down')

        ret = self.set_interface('bond_add_port', f'+{interface}')
        # The kernel will ALWAYS place new bond members in "up" state regardless
        # what the LI is configured for - thus we place the interface in its
        # desired state
        slave.set_admin_state(slave_state)
        return ret

    def del_port(self, interface):
        """
        Remove physical port from bond

        Example:
        >>> from vyos.ifconfig import BondIf
        >>> BondIf('bond0').del_port('eth1')
        """
        return self.set_interface('bond_del_port', f'-{interface}')

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

    def get_mode(self):
        """
        Return bond operation mode.

        Example:
        >>> from vyos.ifconfig import BondIf
        >>> BondIf('bond0').get_mode()
        '802.3ad'
        """
        mode = self.get_interface('bond_mode')
        # mode is now "802.3ad 4", we are only interested in "802.3ad"
        return mode.split()[0]

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

    def set_system_mac(self, mac):
        """
        In an AD system, this specifies the mac-address for the actor in
	    protocol packet exchanges (LACPDUs). The value cannot be NULL or
	    multicast. It is preferred to have the local-admin bit set for this
	    mac but driver does not enforce it. If the value is not given then
	    system defaults to using the masters' mac address as actors' system
	    address.

	    This parameter has effect only in 802.3ad mode and is available through
	    SysFs interface.

        Example:
        >>> from vyos.ifconfig import BondIf
        >>> BondIf('bond0').set_system_mac('00:50:ab:cd:ef:01')
        """
        return self.set_interface('bond_system_mac', mac)

    def update(self, config):
        """ General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface. """

        # use ref-counting function to place an interface into admin down state.
        # set_admin_state_up() must be called the same amount of times else the
        # interface won't come up. This can/should be used to prevent link flapping
        # when changing interface parameters require the interface to be down.
        # We will disable it once before reconfiguration and enable it afterwards.
        if 'shutdown_required' in config:
            self.set_admin_state('down')

        # Specifies the MII link monitoring frequency in milliseconds
        value = config.get('mii_mon_interval')
        self.set_miimon_interval(value)

        # Bonding transmit hash policy
        value = config.get('hash_policy')
        if value: self.set_hash_policy(value)

        # Minimum number of member interfaces
        value = config.get('min_links')
        if value: self.set_min_links(value)

        # Some interface options can only be changed if the interface is
        # administratively down
        if self.get_admin_state() == 'down':
            # Remove ALL bond member interfaces
            for interface in self.get_slaves():
                self.del_port(interface)

                # Restore correct interface status based on config
                if dict_search(f'member.interface.{interface}.disable', config) is not None or \
                   dict_search(f'member.interface_remove.{interface}.disable', config) is not None:
                    Interface(interface).set_admin_state('down')
                else:
                    Interface(interface).set_admin_state('up')

            # Bonding policy/mode - default value, always present
            self.set_mode(config['mode'])

            # LACPDU transmission rate - default value
            if config['mode'] == '802.3ad':
                self.set_lacp_rate(config.get('lacp_rate'))

            if config['mode'] not in ['802.3ad', 'balance-tlb', 'balance-alb']:
                tmp = dict_search('arp_monitor.interval', config)
                value = tmp if (tmp != None) else '0'
                self.set_arp_interval(value)

                # ARP monitor targets need to be synchronized between sysfs and CLI.
                # Unfortunately an address can't be send twice to sysfs as this will
                # result in the following exception:  OSError: [Errno 22] Invalid argument.
                #
                # We remove ALL addresses prior to adding new ones, this will remove
                # addresses manually added by the user too - but as we are limited to 16 adresses
                # from the kernel side this looks valid to me. We won't run into an error
                # when a user added manual adresses which would result in having more
                # then 16 adresses in total.
                arp_tgt_addr = list(map(str, self.get_arp_ip_target().split()))
                for addr in arp_tgt_addr:
                    self.set_arp_ip_target('-' + addr)

                # Add configured ARP target addresses
                value = dict_search('arp_monitor.target', config)
                if isinstance(value, str):
                    value = [value]
                if value:
                    for addr in value:
                        self.set_arp_ip_target('+' + addr)

            # Add (enslave) interfaces to bond
            value = dict_search('member.interface', config)
            for interface in (value or []):
                # if we've come here we already verified the interface
                # does not have an addresses configured so just flush
                # any remaining ones
                Interface(interface).flush_addrs()
                self.add_port(interface)

        # Add system mac address for 802.3ad - default address is all zero
        # mode is always present (defaultValue)
        if config['mode'] == '802.3ad':
            mac = '00:00:00:00:00:00'
            if 'system_mac' in config:
                mac = config['system_mac']
            self.set_system_mac(mac)

        # Primary device interface - must be set after 'mode'
        value = config.get('primary')
        if value: self.set_primary(value)

        # call base class first
        super().update(config)

        # enable/disable EAPoL (Extensible Authentication Protocol over Local Area Network)
        self.set_eapol()
