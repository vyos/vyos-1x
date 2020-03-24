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

from vyos.ifconfig.interface import Interface


# This is an internal implementation class
class VLAN:
    """
    This class handels the creation and removal of a VLAN interface. It serves
    as base class for BondIf and EthernetIf.
    """

    _novlan_remove = lambda : None

    @classmethod
    def enable (cls,adaptee):
        adaptee._novlan_remove = adaptee.remove
        adaptee.remove = cls.remove
        adaptee.add_vlan = cls.add_vlan
        adaptee.del_vlan = cls.del_vlan
        adaptee.definition['vlan'] = True
        return adaptee

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
        ifname = self.config['ifname']

        # Do we have sub interfaces (VLANs)? We apply a regex matching
        # subinterfaces (indicated by a .) of a parent interface.
        #
        # As interfaces need to be deleted "in order" starting from Q-in-Q
        # we delete them first.
        vlan_ifs = [f for f in os.listdir(r'/sys/class/net')
                    if re.match(ifname + r'(?:\.\d+)(?:\.\d+)', f)]

        for vlan in vlan_ifs:
            Interface(vlan).remove()

        # After deleting all Q-in-Q interfaces delete other VLAN interfaces
        # which probably acted as parent to Q-in-Q or have been regular 802.1q
        # interface.
        vlan_ifs = [f for f in os.listdir(r'/sys/class/net')
                    if re.match(ifname + r'(?:\.\d+)', f)]

        for vlan in vlan_ifs:
            # self.__class__ is already VLAN.enabled
            self.__class__(vlan)._novlan_remove()

        # All subinterfaces are now removed, continue on the physical interface
        self._novlan_remove()

    def add_vlan(self, vlan_id, ethertype='', ingress_qos='', egress_qos=''):
        """
        A virtual LAN (VLAN) is any broadcast domain that is partitioned and
        isolated in a computer network at the data link layer (OSI layer 2).
        Use this function to create a new VLAN interface on a given physical
        interface.

        This function creates both 802.1q and 802.1ad (Q-in-Q) interfaces. Proto
        parameter is used to indicate VLAN type.

        A new object of type VLANIf is returned once the interface has been
        created.

        @param ethertype: If specified, create 802.1ad or 802.1q Q-in-Q VLAN
                          interface
        @param ingress_qos: Defines a mapping of VLAN header prio field to the
                            Linux internal packet priority on incoming frames.
        @param ingress_qos: Defines a mapping of Linux internal packet priority
                            to VLAN header prio field but for outgoing frames.

        Example:
        >>> from vyos.ifconfig import MACVLANIf
        >>> i = MACVLANIf('eth0')
        >>> i.add_vlan(10)
        """
        vlan_ifname = self.config['ifname'] + '.' + str(vlan_id)
        if not os.path.exists(f'/sys/class/net/{vlan_ifname}'):
            self._vlan_id = int(vlan_id)

            if ethertype:
                self._ethertype = ethertype
                ethertype = 'proto {}'.format(ethertype)

            # Optional ingress QOS mapping
            opt_i = ''
            if ingress_qos:
                opt_i = 'ingress-qos-map ' + ingress_qos
            # Optional egress QOS mapping
            opt_e = ''
            if egress_qos:
                opt_e = 'egress-qos-map ' + egress_qos

            # create interface in the system
            cmd = 'ip link add link {ifname} name {ifname}.{vlan} type vlan {proto} id {vlan} {opt_e} {opt_i}' \
                .format(ifname=self.config['ifname'], vlan=self._vlan_id, proto=ethertype, opt_e=opt_e, opt_i=opt_i)
            self._cmd(cmd)

        # return new object mapping to the newly created interface
        # we can now work on this object for e.g. IP address setting
        # or interface description and so on
        return self.__class__(vlan_ifname)

    def del_vlan(self, vlan_id):
        """
        Remove VLAN interface from operating system. Removing the interface
        deconfigures all assigned IP addresses and clear possible DHCP(v6)
        client processes.

        Example:
        >>> from vyos.ifconfig import MACVLANIf
        >>> i = MACVLANIf('eth0.10')
        >>> i.del_vlan()
        """
        ifname = self.config['ifname']
        self.__class__(f'{ifname}.{vlan_id}')._novlan_remove()
