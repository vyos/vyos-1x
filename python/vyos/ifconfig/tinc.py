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
class TincIf(Interface):
    default = {
        'type': 'tinc',
    }
    definition = {
        **Interface.definition,
        **{
            'section': 'tinc',
            'prefixes': ['tinc'],
            'bridgeable': True,
            'eternal': '(tinc)[0-9]+$',
            'bondable': True,
            'broadcast': True
        },
    }
    
    def update(self, config):
        # Enable/Disable of an interface must always be done at the end of the
        # derived class to make use of the ref-counting set_admin_state()
        # function. We will only enable the interface if 'up' was called as
        # often as 'down'. This is required by some interface implementations
        # as certain parameters can only be changed when the interface is
        # in admin-down state. This ensures the link does not flap during
        # reconfiguration.
        super().update(config)
        state = 'down' if 'disable' in config else 'up'
        self.set_admin_state(state)

    def remove(self):
        self.set_admin_state('down')
        super().remove()
