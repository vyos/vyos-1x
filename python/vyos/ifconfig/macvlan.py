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
    }
    definition = {
        **Interface.definition,
        **{
            'section': 'pseudo-ethernet',
            'prefixes': ['peth', ],
        },
    }
    options = Interface.options + ['link', 'mode']

    def _create(self):
        cmd = 'ip link add {ifname} link {link} type macvlan mode {mode}'.format(
            **self.config)
        self._cmd(cmd)

    @staticmethod
    def get_config():
        """
        VXLAN interfaces require a configuration when they are added using
        iproute2. This static method will provide the configuration dictionary
        used by this class.

        Example:
        >> dict = MACVLANIf().get_config()
        """
        config = {
            'address': '',
            'link': 0,
            'mode': ''
        }
        return config

    def set_mode(self, mode):
        """
        """

        cmd = 'ip link set dev {} type macvlan mode {}'.format(
            self.config['ifname'], mode)
        return self._cmd(cmd)
