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

from errno import EEXIST

from pyroute2.netlink.exceptions import NetlinkError

from vyos.ifconfig.interface import Interface
from vyos.netlink.ovpn import add_ovpn_interface

@Interface.register
class VTunIf(Interface):
    definition = {
        **Interface.definition,
        **{
            'section': 'openvpn',
            'prefixes': ['vtun', ],
            'bridgeable': True,
        },
    }

    def _create(self):
        """ Depending on OpenVPN operation mode the interface is created
        immediately (e.g. Server mode) or once the connection to the server is
        established (client mode). The latter will only be brought up once the
        server can be reached, thus we might need to create this interface in
        advance for the service to be operational. """
        # An offloaded data path lives in the "ovpn" Kernel module, and OpenVPN
        # declines the offload when it finds a device of any other type. The
        # operating mode is fixed at creation time, so it has to be set here.
        if 'dco' in self.config.get('offload', {}):
            # a raw option can still make OpenVPN decline the offload, and it
            # can not use an "ovpn" device then - leave the interface to it
            if 'openvpn_option' in self.config:
                return None

            try:
                return add_ovpn_interface(
                    self.ifname, self.config.get('mode') == 'server'
                )
            except NetlinkError as e:
                if e.code != EEXIST:
                    raise
                # interface created by OpenVPN daemon in the meantime ...
                return None

        try:
            cmd = ['openvpn', '--mktun', '--dev-type', self.config['device_type'],
                   '--dev', self.ifname]
            return self._cmdl(cmd)
        except PermissionError:
            # interface created by OpenVPN daemon in the meantime ...
            pass

    def add_addr(self, addr):
        # IP addresses are managed by OpenVPN daemon
        pass

    def del_addr(self, addr):
        # IP addresses are managed by OpenVPN daemon
        pass
