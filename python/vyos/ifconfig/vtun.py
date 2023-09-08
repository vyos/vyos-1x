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
            'eternal': 'vtun[0-9]+$',
            'bridgeable': True,
        },
    }

    def _create(self):
        # Interface is managed by OpenVPN daemon
        pass

    def _delete(self):
        # Interface is managed by OpenVPN daemon
        pass

    def add_addr(self, addr):
        # IP addresses are managed by OpenVPN daemon
        pass

    def del_addr(self, addr):
        # IP addresses are managed by OpenVPN daemon
        pass
