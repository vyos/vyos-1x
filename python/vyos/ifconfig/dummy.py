# Copyright 2019-2021 VyOS maintainers and contributors <maintainers@vyos.io>
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
class DummyIf(Interface):
    """
    A dummy interface is entirely virtual like, for example, the loopback
    interface. The purpose of a dummy interface is to provide a device to route
    packets through without actually transmitting them.
    """

    iftype = 'dummy'
    definition = {
        **Interface.definition,
        **{
            'section': 'dummy',
            'prefixes': ['dum', ],
        },
    }
