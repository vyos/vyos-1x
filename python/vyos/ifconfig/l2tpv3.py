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


class L2TPv3If(Interface):
    """
    The Linux bonding driver provides a method for aggregating multiple network
    interfaces into a single logical "bonded" interface. The behavior of the
    bonded interfaces depends upon the mode; generally speaking, modes provide
    either hot standby or load balancing services. Additionally, link integrity
    monitoring may be performed.
    """

    options = Interface.options + \
        ['tunnel_id', 'peer_tunnel_id', 'local_port', 'remote_port',
            'encapsulation', 'local_address', 'remote_address']
    default = {
        'type': 'l2tp',
    }

    def __init__(self, ifname, **kargs):
        super().__init__(ifname, **kargs)

    def _create(self):
        # create tunnel interface
        cmd = 'ip l2tp add tunnel tunnel_id {} '.format(config['tunnel_id'])
        cmd += 'peer_tunnel_id {} '.format(config['peer_tunnel_id'])
        cmd += 'udp_sport {} '.format(config['local_port'])
        cmd += 'udp_dport {} '.format(config['remote_port'])
        cmd += 'encap {} '.format(config['encapsulation'])
        cmd += 'local {} '.format(config['local_address'])
        cmd += 'remote {} '.format(config['remote_address'])
        self._cmd(cmd)

        # setup session
        cmd = 'ip l2tp add session name {} '.format(self.config['ifname'])
        cmd += 'tunnel_id {} '.format(config['tunnel_id'])
        cmd += 'session_id {} '.format(config['session_id'])
        cmd += 'peer_session_id  {} '.format(config['peer_session_id'])
        self._cmd(cmd)

        # interface is always A/D down. It needs to be enabled explicitly
        self.set_state('down')

    def remove(self):
        """
        Remove interface from operating system. Removing the interface
        deconfigures all assigned IP addresses.
        Example:
        >>> from vyos.ifconfig import L2TPv3If
        >>> i = L2TPv3If('l2tpeth0')
        >>> i.remove()
        """

        if os.path.exists('/sys/class/net/{}'.format(self.config['ifname'])):
            # interface is always A/D down. It needs to be enabled explicitly
            self.set_state('down')

            if self._config['tunnel_id'] and self._config['session_id']:
                cmd = 'ip l2tp del session tunnel_id {} '.format(
                    self._config['tunnel_id'])
                cmd += 'session_id {} '.format(self._config['session_id'])
                self._cmd(cmd)

            if self._config['tunnel_id']:
                cmd = 'ip l2tp del tunnel tunnel_id {} '.format(
                    self._config['tunnel_id'])
                self._cmd(cmd)

    @staticmethod
    def get_config():
        """
        L2TPv3 interfaces require a configuration when they are added using
        iproute2. This static method will provide the configuration dictionary
        used by this class.

        Example:
        >> dict = L2TPv3If().get_config()
        """
        config = {
            'peer_tunnel_id': '',
            'local_port': 0,
            'remote_port': 0,
            'encapsulation': 'udp',
            'local_address': '',
            'remote_address': '',
            'session_id': '',
            'tunnel_id': '',
            'peer_session_id': ''
        }
        return config
