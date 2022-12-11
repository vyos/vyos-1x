# Copyright 2022 VyOS maintainers and contributors <maintainers@vyos.io>
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
class SSTPCIf(Interface):
    iftype = 'sstpc'
    definition = {
        **Interface.definition,
        **{
            'section': 'sstpc',
            'prefixes': ['sstpc', ],
            'eternal': 'sstpc[0-9]+$',
        },
    }

    def _create(self):
        # we can not create this interface as it is managed outside
        pass

    def _delete(self):
        # we can not create this interface as it is managed outside
        pass

    def get_mac(self):
        """ Get a synthetic MAC address. """
        return self.get_mac_synthetic()
