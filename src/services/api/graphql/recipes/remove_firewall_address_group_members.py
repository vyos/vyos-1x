# Copyright 2021 VyOS maintainers and contributors <maintainers@vyos.io>
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
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

from . session import Session

class RemoveFirewallAddressGroupMembers(Session):
    def __init__(self, session, data):
        super().__init__(session, data)

    # Define any custom processing of parameters here by overriding
    # configure:
    #
    # def configure(self):
    #     self._data = transform_data(self._data)
    #     super().configure()
    #     self.clean_up()

    def configure(self):
        super().configure()

        group_name = self._data['name']
        path = ['firewall', 'group', 'address-group', group_name]
        self.delete_path_if_childless(path)
