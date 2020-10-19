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
class VTunIf(Interface):
    default = {
        'type': 'vtun',
        'device_type': 'tun',
    }
    definition = {
        **Interface.definition,
        **{
            'section': 'openvpn',
            'prefixes': ['vtun', ],
            'bridgeable': True,
        },
    }
    options = Interface.options + ['device_type']

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

    def update(self, config):
        """ General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface. """

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
