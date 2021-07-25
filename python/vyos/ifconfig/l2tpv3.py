# Copyright 2019-2021 VyOS maintainers and contributors <maintainers@vyos.io>
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

from vyos.ifconfig.interface import Interface

@Interface.register
class L2TPv3If(Interface):
    """
    The Linux bonding driver provides a method for aggregating multiple network
    interfaces into a single logical "bonded" interface. The behavior of the
    bonded interfaces depends upon the mode; generally speaking, modes provide
    either hot standby or load balancing services. Additionally, link integrity
    monitoring may be performed.
    """
    iftype = 'l2tp'
    definition = {
        **Interface.definition,
        **{
            'section': 'l2tpeth',
            'prefixes': ['l2tpeth', ],
            'bridgeable': True,
        }
    }

    def _create(self):
        # create tunnel interface
        cmd = 'ip l2tp add tunnel tunnel_id {tunnel_id}'
        cmd += ' peer_tunnel_id {peer_tunnel_id}'
        cmd += ' udp_sport {source_port}'
        cmd += ' udp_dport {destination_port}'
        cmd += ' encap {encapsulation}'
        cmd += ' local {source_address}'
        cmd += ' remote {remote}'
        self._cmd(cmd.format(**self.config))

        # setup session
        cmd = 'ip l2tp add session name {ifname}'
        cmd += ' tunnel_id {tunnel_id}'
        cmd += ' session_id {session_id}'
        cmd += ' peer_session_id {peer_session_id}'
        self._cmd(cmd.format(**self.config))

        # No need for interface shut down. There exist no function to permanently enable tunnel.
        # But you can disable interface permanently with shutdown/disable command.
        self.set_admin_state('up')

    def remove(self):
        """
        Remove interface from operating system. Removing the interface
        deconfigures all assigned IP addresses.
        Example:
        >>> from vyos.ifconfig import L2TPv3If
        >>> i = L2TPv3If('l2tpeth0')
        >>> i.remove()
        """

        if self.exists(self.ifname):
            # interface is always A/D down. It needs to be enabled explicitly
            self.set_admin_state('down')

            if {'tunnel_id', 'session_id'} <= set(self.config):
                cmd = 'ip l2tp del session tunnel_id {tunnel_id}'
                cmd += ' session_id {session_id}'
                self._cmd(cmd.format(**self.config))

            if 'tunnel_id' in self.config:
                cmd = 'ip l2tp del tunnel tunnel_id {tunnel_id}'
                self._cmd(cmd.format(**self.config))
