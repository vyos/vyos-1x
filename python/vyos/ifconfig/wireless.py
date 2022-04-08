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
class WiFiIf(Interface):
    """
    Handle WIFI/WLAN interfaces.
    """
    iftype = 'wifi'
    definition = {
        **Interface.definition,
        **{
            'section': 'wireless',
            'prefixes': ['wlan', ],
            'bridgeable': True,
        }
    }
    def _create(self):
        # all interfaces will be added in monitor mode
        cmd = 'iw phy {physical_device} interface add {ifname} type monitor'
        self._cmd(cmd.format(**self.config))

        # wireless interface is administratively down by default
        self.set_admin_state('down')

    def _delete(self):
        cmd = 'iw dev {ifname} del' \
            .format(**self.config)
        self._cmd(cmd)

    def update(self, config):
        """ General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface. """

        # We can not call add_to_bridge() until wpa_supplicant is running, thus
        # we will remove the key from the config dict and react to this special
        # case in this derived class.
        # re-add ourselves to any bridge we might have fallen out of
        bridge_member = None
        if 'is_bridge_member' in config:
            bridge_member = config['is_bridge_member']
            del config['is_bridge_member']

        # call base class first
        super().update(config)

        # re-add ourselves to any bridge we might have fallen out of
        if bridge_member:
            self.add_to_bridge(bridge_member)
