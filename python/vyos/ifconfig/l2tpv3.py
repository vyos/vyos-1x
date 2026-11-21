# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

from ipaddress import ip_address
from time import sleep
from time import time

from vyos.utils.misc import wait_for
from vyos.utils.process import ip_cmd
from vyos.utils.process import rc_cmd
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

# "ip l2tp show" ignores a tunnel_id argument, hence the filtering below
def get_l2tp_tunnel(tunnel_id: int) -> dict | None:
    """ Return the Kernel L2TPv3 tunnel with the given ID or None """
    tunnels = ip_cmd('l2tp show tunnel') or []
    return next((t for t in tunnels if t['tunnel_id'] == int(tunnel_id)), None)

def get_l2tp_sessions(tunnel_id: int | None = None) -> list:
    """ Return the Kernel L2TPv3 sessions, optionally of one tunnel only """
    sessions = ip_cmd('l2tp show session') or []
    if tunnel_id is None:
        return sessions
    return [s for s in sessions if s['tunnel_id'] == int(tunnel_id)]

@Interface.register
class L2TPv3If(Interface):
    """
    The Linux bonding driver provides a method for aggregating multiple network
    interfaces into a single logical "bonded" interface. The behavior of the
    bonded interfaces depends upon the mode; generally speaking, modes provide
    either hot standby or load balancing services. Additionally, link integrity
    monitoring may be performed.
    """
    definition = {
        **Interface.definition,
        **{
            'section': 'l2tpv3',
            'prefixes': ['l2tpeth', ],
            'bridgeable': True,
        }
    }

    # The Kernel deletes tunnels and sessions asynchronously, until then they
    # are still listed - a session added to such a tunnel fails or goes along
    def _del_tunnel(self, tunnel_id: int):
        self._cmdl(['ip', 'l2tp', 'del', 'tunnel', 'tunnel_id', str(tunnel_id)])
        if not wait_for(lambda: get_l2tp_tunnel(tunnel_id) is None, interval=0.1):
            raise OSError(f'L2TPv3 tunnel {tunnel_id} was not deleted')

    def _del_session(self, tunnel_id: int, session_id: int):
        self._cmdl(['ip', 'l2tp', 'del', 'session', 'tunnel_id', str(tunnel_id),
                    'session_id', str(session_id)])
        if not wait_for(lambda: all(s['session_id'] != session_id
                                    for s in get_l2tp_sessions(tunnel_id)),
                        interval=0.1):
            raise OSError(f'L2TPv3 session {session_id} was not deleted')

    def _tunnel_matches_config(self, tunnel: dict) -> bool:
        config = self.config
        if (tunnel['encap'].lower() != config['encapsulation']
                or tunnel['peer_tunnel'] != int(config['peer_tunnel_id'])
                or ip_address(tunnel['local']) != ip_address(config['source_address'])
                or ip_address(tunnel['peer']) != ip_address(config['remote'])):
            return False
        if config['encapsulation'] == 'udp':
            return (tunnel['local_port'] == int(config['source_port'])
                    and tunnel['peer_port'] == int(config['destination_port']))
        return True

    def _create(self):
        # create tunnel interface
        cmd = 'ip l2tp add tunnel tunnel_id {tunnel_id}'
        cmd += ' peer_tunnel_id {peer_tunnel_id}'
        cmd += ' udp_sport {source_port}'
        cmd += ' udp_dport {destination_port}'
        cmd += ' encap {encapsulation}'
        cmd += ' local {source_address}'
        cmd += ' remote {remote}'
        # iproute2 reads an ID with a leading 0 as octal, the CLI value is decimal
        ids = {key: int(self.config[key]) for key in
               ['tunnel_id', 'peer_tunnel_id', 'session_id', 'peer_session_id']}
        c = cmd.format(**{**self.config, **ids})
        tunnel_id = ids['tunnel_id']
        # Interfaces can share a tunnel, each one with its own session - only
        # the first one creates it. A tunnel not matching the config is replaced,
        # the config is the truth: verify() demands identical settings of all
        # interfaces sharing it, their sessions go along and are recreated on
        # their apply.
        tunnel = get_l2tp_tunnel(tunnel_id)
        if tunnel and not self._tunnel_matches_config(tunnel):
            self._del_tunnel(tunnel_id)
            tunnel = None
        tunnel_created = False
        if not tunnel:
            # wait until the local/remote address is available, but no more 10 sec.
            if not wait_for_add_l2tpv3(cmd=c):
                raise OSError(f'Could not create L2TPv3 tunnel {tunnel_id}')
            tunnel_created = True

        # setup session
        cmd = ['ip', 'l2tp', 'add', 'session', 'name', self.ifname,
               'tunnel_id', str(tunnel_id),
               'session_id', str(ids['session_id']),
               'peer_session_id', str(ids['peer_session_id'])]
        # iproute2 reports why on stderr, which _cmdl() does not capture
        code, out = rc_cmd(cmd, flag=self.debug, vrf=self.config.get('vrf'),
                           netns=self.config.get('netns'))
        if code:
            # without session there is no interface, remove() could not find
            # the tunnel anymore
            if tunnel_created:
                self._del_tunnel(tunnel_id)
            raise OSError(code, f'Could not create L2TPv3 session '
                                f'{ids["session_id"]} in tunnel {tunnel_id}: {out}')

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

            # Delete the session this interface holds in the Kernel, the config
            # may already carry a changed tunnel or session ID
            session = next((s for s in get_l2tp_sessions()
                            if s.get('interface') == self.ifname), None)
            if session:
                tunnel_id = session['tunnel_id']
                self._del_session(tunnel_id, session['session_id'])
                # deleting the tunnel would take the sessions of other
                # interfaces sharing it along
                if not get_l2tp_sessions(tunnel_id):
                    self._del_tunnel(tunnel_id)

            # No need to call the baseclass as the interface is now already gone
