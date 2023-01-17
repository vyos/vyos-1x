# Copyright 2023 VyOS maintainers and contributors <maintainers@vyos.io>
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
class InputIf(Interface):
    """
    The Intermediate Functional Block (ifb) pseudo network interface acts as a
    QoS concentrator for multiple different sources of traffic. Packets from
    or to other interfaces have to be redirected to it using the mirred action
    in order to be handled, regularly routed traffic will be dropped. This way,
    a single stack of qdiscs, classes and filters can be shared between
    multiple interfaces.
    """

    iftype = 'ifb'
    definition = {
        **Interface.definition,
        **{
            'section': 'input',
            'prefixes': ['ifb', ],
        },
    }
