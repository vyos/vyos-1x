# Copyright 2019-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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
class ThunderboltIf(Interface):
    """
    Handle Thunderbolt Network interfaces
    """

    iftype = 'thunderbolt'
    definition = {
        **Interface.definition,
        **{
            'section': 'thunderbolt',
            'prefixes': ['thunderbolt', ],
            'bondable': False,
            'broadcast': True,
            'bridgeable': True,
        },
    }

    def _create(self):
        pass # TODO: actually create systemd/udev files for the interface
