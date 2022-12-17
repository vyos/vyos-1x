# Copyright 2019-2022 VyOS maintainers and contributors <maintainers@vyos.io>
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
class MACVLANIf(Interface):
    """
    Abstraction of a Linux MACvlan interface
    """
    iftype = 'macvlan'
    definition = {
        **Interface.definition,
        **{
            'section': 'pseudo-ethernet',
            'prefixes': ['peth', ],
        },
    }

    def _create(self):
        """
        Create MACvlan interface in OS kernel. Interface is administrative
        down by default.
        """
        # please do not change the order when assembling the command
        cmd = 'ip link add {ifname} link {source_interface} type {type} mode {mode}'
        self._cmd(cmd.format(**self.config))

        # interface is always A/D down. It needs to be enabled explicitly
        self.set_admin_state('down')

    def set_mode(self, mode):
        ifname = self.config['ifname']
        cmd = f'ip link set dev {ifname} type macvlan mode {mode}'
        return self._cmd(cmd)
