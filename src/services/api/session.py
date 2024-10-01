# Copyright 2024 VyOS maintainers and contributors <maintainers@vyos.io>
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


class SessionState:
    # pylint: disable=attribute-defined-outside-init
    # pylint: disable=too-many-instance-attributes,too-few-public-methods

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SessionState, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.session = None
        self.keys = []
        self.id = None
        self.rest = False
        self.debug = False
        self.strict = False
        self.graphql = False
        self.origins = []
        self.introspection = False
        self.auth_type = None
        self.token_exp = None
        self.secret_len = None
