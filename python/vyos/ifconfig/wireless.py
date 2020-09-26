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

from vyos.ifconfig.interface import Interface

@Interface.register
class WiFiIf(Interface):
    """
    Handle WIFI/WLAN interfaces.
    """

    default = {
        'type': 'wifi',
        'phy': '',
        'wds': 'off',
    }

    definition = {
        **Interface.definition,
        **{
            'section': 'wireless',
            'prefixes': ['wlan', ],
            'bridgeable': True,
        }
    }

    options = Interface.options + \
        ['phy', 'op_mode']

    _command_set = {**Interface._command_set, **{
        '4addr': {
            'shellcmd': 'iw dev {ifname} set 4addr {value}',
        },
    }}

    def _create(self):
        # all interfaces will be added in monitor mode
        cmd = 'iw phy {phy} interface add {ifname} type monitor 4addr {wds}' \
            .format(**self.config)
        self._cmd(cmd)

        # wireless interface is administratively down by default
        self.set_admin_state('down')

    def _delete(self):
        cmd = 'iw dev {ifname} del' \
            .format(**self.config)
        self._cmd(cmd)

    def set_4aadr_mode(self, state):
        return self.set_interface('4addr', state)

    def update(self, config):
        """ General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface. """

        self.set_4aadr_mode('on' if 'wds' in config else 'off')

        # call base class first
        super().update(config)

        # Enable/Disable of an interface must always be done at the end of the
        # derived class to make use of the ref-counting set_admin_state()
        # function. We will only enable the interface if 'up' was called as
        # often as 'down'. This is required by some interface implementations
        # as certain parameters can only be changed when the interface is
        # in admin-down state. This ensures the link does not flap during
        # reconfiguration.
        state = 'down' if 'disable' in config else 'up'
        self.set_admin_state(state)


@Interface.register
class WiFiModemIf(WiFiIf):
    definition = {
        **WiFiIf.definition,
        **{
            'section': 'wirelessmodem',
            'prefixes': ['wlm', ],
        }
    }
