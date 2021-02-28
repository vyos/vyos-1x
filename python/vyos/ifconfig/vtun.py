# Copyright 2020-2021 VyOS maintainers and contributors <maintainers@vyos.io>
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
class VTunIf(Interface):
    iftype = 'vtun'
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
        try:
            cmd = 'openvpn --mktun --dev-type {device_type} --dev {ifname}'.format(**self.config)
            return self._cmd(cmd)
        except PermissionError:
            # interface created by OpenVPN daemon in the meantime ...
            pass

    def add_addr(self, addr):
        # IP addresses are managed by OpenVPN daemon
        pass

    def del_addr(self, addr):
        # IP addresses are managed by OpenVPN daemon
        pass
