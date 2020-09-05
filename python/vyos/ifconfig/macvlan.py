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

from copy import deepcopy

from vyos.ifconfig.interface import Interface
from vyos.ifconfig.vlan import VLAN


@Interface.register
@VLAN.enable
class MACVLANIf(Interface):
    """
    Abstraction of a Linux MACvlan interface
    """

    default = {
        'type': 'macvlan',
        'address': '',
        'source_interface': '',
        'mode': '',
    }
    definition = {
        **Interface.definition,
        **{
            'section': 'pseudo-ethernet',
            'prefixes': ['peth', ],
        },
    }
    options = Interface.options + \
        ['source_interface', 'mode']

    def _create(self):
        # please do not change the order when assembling the command
        cmd = 'ip link add {ifname}'
        if self.config['source_interface']:
            cmd += ' link {source_interface}'
        cmd += ' type macvlan'
        if self.config['mode']:
            cmd += ' mode {mode}'
        self._cmd(cmd.format(**self.config))

    def set_mode(self, mode):
        ifname = self.config['ifname']
        cmd = f'ip link set dev {ifname} type macvlan mode {mode}'
        return self._cmd(cmd)

    @classmethod
    def get_config(cls):
        """
        MACVLAN interfaces require a configuration when they are added using
        iproute2. This method will provide the configuration dictionary used
        by this class.

        Example:
        >> dict = MACVLANIf().get_config()
        """
        return deepcopy(cls.default)

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
