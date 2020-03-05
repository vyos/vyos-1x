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

from vyos.validate import *


class STPIf(Interface):
    """
    A spanning-tree capable interface. This applies only to bridge port member
    interfaces!
    """
    _sysfs_set = {**Interface._sysfs_set, **{
        'path_cost': {
            # XXX: we should set a maximum
            'validate': assert_positive,
            'location': '/sys/class/net/{ifname}/brport/path_cost',
            'errormsg': '{ifname} is not a bridge port member'
        },
        'path_priority': {
            # XXX: we should set a maximum
            'validate': assert_positive,
            'location': '/sys/class/net/{ifname}/brport/priority',
            'errormsg': '{ifname} is not a bridge port member'
        },
    }}

    default = {
        'type': 'stp',
    }

    def __init__(self, ifname, **kargs):
        super().__init__(ifname, **kargs)

    def set_path_cost(self, cost):
        """
        Set interface path cost, only relevant for STP enabled interfaces

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_path_cost(4)
        """
        self.set_interface('path_cost', cost)

    def set_path_priority(self, priority):
        """
        Set interface path priority, only relevant for STP enabled interfaces

        Example:

        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').set_path_priority(4)
        """
        self.set_interface('path_priority', priority)
