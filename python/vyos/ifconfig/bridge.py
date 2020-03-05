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

class BridgeIf(Interface):
    """
    A bridge is a way to connect two Ethernet segments together in a protocol
    independent way. Packets are forwarded based on Ethernet address, rather
    than IP address (like a router). Since forwarding is done at Layer 2, all
    protocols can go transparently through a bridge.

    The Linux bridge code implements a subset of the ANSI/IEEE 802.1d standard.
    """

    _sysfs_set = {**Interface._sysfs_set, **{
        'ageing_time': {
            'validate': assert_positive,
            'convert': lambda t: int(t) * 100,
            'location': '/sys/class/net/{ifname}/bridge/ageing_time',
        },
        'forward_delay': {
            'validate': assert_positive,
            'convert': lambda t: int(t) * 100,
            'location': '/sys/class/net/{ifname}/bridge/forward_delay',
        },
        'hello_time': {
            'validate': assert_positive,
            'convert': lambda t: int(t) * 100,
            'location': '/sys/class/net/{ifname}/bridge/hello_time',
        },
        'max_age': {
            'validate': assert_positive,
            'convert': lambda t: int(t) * 100,
            'location': '/sys/class/net/{ifname}/bridge/max_age',
        },
        'priority': {
            'validate': assert_positive,
            'location': '/sys/class/net/{ifname}/bridge/priority',
        },
        'stp': {
            'validate': assert_boolean,
            'location': '/sys/class/net/{ifname}/bridge/stp_state',
        },
        'multicast_querier': {
            'validate': assert_boolean,
            'location': '/sys/class/net/{ifname}/bridge/multicast_querier',
        },
    }}

    _command_set = {**Interface._command_set, **{
        'add_port': {
            'shellcmd': 'ip link set dev {value} master {ifname}',
        },
        'del_port': {
            'shellcmd': 'ip link set dev {value} nomaster',
        },
    }}

    default = {
        'type': 'bridge',
    }

    def __init__(self, ifname, **kargs):
        super().__init__(ifname, **kargs)

    def set_ageing_time(self, time):
        """
        Set bridge interface MAC address aging time in seconds. Internal kernel
        representation is in centiseconds. Kernel default is 300 seconds.

        Example:
        >>> from vyos.ifconfig import BridgeIf
        >>> BridgeIf('br0').ageing_time(2)
        """
        self.set_interface('ageing_time', time)

    def set_forward_delay(self, time):
        """
        Set bridge forwarding delay in seconds. Internal Kernel representation
        is in centiseconds.

        Example:
        >>> from vyos.ifconfig import BridgeIf
        >>> BridgeIf('br0').forward_delay(15)
        """
        self.set_interface('forward_delay', time)

    def set_hello_time(self, time):
        """
        Set bridge hello time in seconds. Internal Kernel representation
        is in centiseconds.

        Example:
        >>> from vyos.ifconfig import BridgeIf
        >>> BridgeIf('br0').set_hello_time(2)
        """
        self.set_interface('hello_time', time)

    def set_max_age(self, time):
        """
        Set bridge max message age in seconds. Internal Kernel representation
        is in centiseconds.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').set_max_age(30)
        """
        self.set_interface('max_age', time)

    def set_priority(self, priority):
        """
        Set bridge max aging time in seconds.

        Example:
        >>> from vyos.ifconfig import BridgeIf
        >>> BridgeIf('br0').set_priority(8192)
        """
        self.set_interface('priority', priority)

    def set_stp(self, state):
        """
        Set bridge STP (Spanning Tree) state. 0 -> STP disabled, 1 -> STP enabled

        Example:
        >>> from vyos.ifconfig import BridgeIf
        >>> BridgeIf('br0').set_stp(1)
        """
        self.set_interface('stp', state)

    def set_multicast_querier(self, enable):
        """
        Sets whether the bridge actively runs a multicast querier or not. When a
        bridge receives a 'multicast host membership' query from another network
        host, that host is tracked based on the time that the query was received
        plus the multicast query interval time.

        Use enable=1 to enable or enable=0 to disable

        Example:
        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').set_multicast_querier(1)
        """
        self.set_interface('multicast_querier', enable)

    def add_port(self, interface):
        """
        Add physical interface to bridge (member port)

        Example:
        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').add_port('eth0')
        >>> BridgeIf('br0').add_port('eth1')
        """
        return self.set_interface('add_port', interface)

    def del_port(self, interface):
        """
        Remove member port from bridge instance.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').del_port('eth1')
        """
        return self.set_interface('del_port', interface)
