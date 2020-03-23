# Copyright 2020 VyOS maintainers and contributors <maintainers@vyos.io>
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

from vyos.ifconfig.vlan import VLANIf

class WiFiIf(VLANIf):
    """
    Handle WIFI/WLAN interfaces.
    """

    options = ['phy', 'op_mode']

    default = {
        'type': 'wifi',
        'phy': 'phy0'
    }

    def _create(self):
        # all interfaces will be added in monitor mode
        cmd = 'iw phy {phy} interface add {ifname} type monitor' \
            .format(**self.config)
        self._cmd(cmd)

    def _delete(self):
        cmd = 'iw dev {ifname} del' \
            .format(**self.config)
        self._cmd(cmd)

    @staticmethod
    def get_config():
        """
        WiFi interfaces require a configuration when they are added using
        iw (type/phy). This static method will provide the configuration
        ictionary used by this class.

        Example:
        >> conf = WiFiIf().get_config()
        """
        config = {
            'phy': 'phy0'
        }
        return config
