# Copyright 2019-2023 VyOS maintainers and contributors <maintainers@vyos.io>
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

from time import sleep
from time import time

from vyos.utils.process import run
from vyos.ifconfig.interface import Interface

def wait_for_add_l2tpv3(timeout=10, sleep_interval=1, cmd=None):
    '''
    In some cases, we need to wait until local address is assigned.
    And only then can the l2tpv3 tunnel be configured.
    For example when ipv6 address in tentative state
    or we wait for some routing daemon for remote address.
    '''
    start_time = time()
    test_command = cmd
    while True:
        if (start_time + timeout) < time():
            return None
        result = run(test_command)
        if result == 0:
            return True
        sleep(sleep_interval)

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
        c = cmd.format(**self.config)
        # wait until the local/remote address is available, but no more 10 sec.
        wait_for_add_l2tpv3(cmd=c)

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
            self.set_admin_state('down')

            # remove all assigned IP addresses from interface - this is a bit redundant
            # as the kernel will remove all addresses on interface deletion
            self.flush_addrs()

            # remove interface from conntrack VRF interface map, here explicitly and do not
            # rely on the base class implementation as the interface will
            # vanish as soon as the l2tp session is deleted
            self._del_interface_from_ct_iface_map()

            if {'tunnel_id', 'session_id'} <= set(self.config):
                cmd = 'ip l2tp del session tunnel_id {tunnel_id}'
                cmd += ' session_id {session_id}'
                self._cmd(cmd.format(**self.config))

            if 'tunnel_id' in self.config:
                cmd = 'ip l2tp del tunnel tunnel_id {tunnel_id}'
                self._cmd(cmd.format(**self.config))

            # No need to call the baseclass as the interface is now already gone
