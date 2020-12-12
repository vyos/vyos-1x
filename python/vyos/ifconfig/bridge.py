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

from netifaces import interfaces
import json

from vyos.ifconfig.interface import Interface
from vyos.validate import assert_boolean
from vyos.validate import assert_positive
from vyos.util import cmd
from vyos.util import dict_search
from vyos.configdict import get_vlan_ids

@Interface.register
class BridgeIf(Interface):
    """
    A bridge is a way to connect two Ethernet segments together in a protocol
    independent way. Packets are forwarded based on Ethernet address, rather
    than IP address (like a router). Since forwarding is done at Layer 2, all
    protocols can go transparently through a bridge.

    The Linux bridge code implements a subset of the ANSI/IEEE 802.1d standard.
    """

    default = {
        'type': 'bridge',
    }
    definition = {
        **Interface.definition,
        **{
            'section': 'bridge',
            'prefixes': ['br', ],
            'broadcast': True,
            'vlan': True,
        },
    }
    
    _sysfs_get = {
        **Interface._sysfs_get,**{
            'vlan_filter': {
                'location': '/sys/class/net/{ifname}/bridge/vlan_filtering'
            }
        }
    }

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
        'vlan_filter': {
            'validate': assert_boolean,
            'location': '/sys/class/net/{ifname}/bridge/vlan_filtering',
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
    
    def get_vlan_filter(self):
        """
        Get the status of the bridge VLAN filter
        """
        
        return self.get_interface('vlan_filter')


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

    def set_vlan_filter(self, state):
        """
        Set bridge Vlan Filter state. 0 -> Vlan Filter disabled, 1 -> Vlan Filter enabled

        Example:
        >>> from vyos.ifconfig import BridgeIf
        >>> BridgeIf('br0').set_vlan_filter(1)
        """
        self.set_interface('vlan_filter', state)

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
        try:
            return self.set_interface('add_port', interface)
        except:
            from vyos import ConfigError
            raise ConfigError('Error: Device does not allow enslaving to a bridge.')

    def del_port(self, interface):
        """
        Remove member port from bridge instance.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').del_port('eth1')
        """
        return self.set_interface('del_port', interface)

    def update(self, config):
        """ General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface. """

        # call base class first
        super().update(config)

        ifname = config['ifname']

        # Set ageing time
        value = config.get('aging')
        self.set_ageing_time(value)

        # set bridge forward delay
        value = config.get('forwarding_delay')
        self.set_forward_delay(value)

        # set hello time
        value = config.get('hello_time')
        self.set_hello_time(value)

        # set max message age
        value = config.get('max_age')
        self.set_max_age(value)

        # set bridge priority
        value = config.get('priority')
        self.set_priority(value)

        # enable/disable spanning tree
        value = '1' if 'stp' in config else '0'
        self.set_stp(value)

        # enable or disable IGMP querier
        tmp = dict_search('igmp.querier', config)
        value = '1' if (tmp != None) else '0'
        self.set_multicast_querier(value)

        # remove interface from bridge
        tmp = dict_search('member.interface_remove', config)
        for member in (tmp or []):
            if member in interfaces():
                self.del_port(member)
        vlan_filter = 0

        vlan_del = set()
        vlan_add = set()

        tmp = dict_search('member.interface', config)
        if tmp:
            if self.get_vlan_filter():
                bridge_vlan_ids = get_vlan_ids(ifname)
                # Delete VLAN ID for the bridge
                if 1 in bridge_vlan_ids:
                    bridge_vlan_ids.remove(1)
                for vlan in bridge_vlan_ids:
                    vlan_del.add(str(vlan))
            
            for interface, interface_config in tmp.items():
                # if interface does yet not exist bail out early and
                # add it later
                if interface not in interfaces():
                    continue

                # Bridge lower "physical" interface
                lower = Interface(interface)

                # If we've come that far we already verified the interface does
                # not have any addresses configured by CLI so just flush any
                # remaining ones
                lower.flush_addrs()
                # enslave interface port to bridge
                self.add_port(interface)

                # set bridge port path cost
                if 'cost' in interface_config:
                    value = interface_config.get('cost')
                    lower.set_path_cost(value)

                # set bridge port path priority
                if 'priority' in interface_config:
                    value = interface_config.get('priority')
                    lower.set_path_priority(value)

                tmp = dict_search('native_vlan_removed', interface_config)

                for vlan_id in (tmp or []):
                    cmd = f'bridge vlan del dev {interface} vid {vlan_id}'
                    self._cmd(cmd)
                    cmd = f'bridge vlan add dev {interface} vid 1 pvid untagged master'
                    self._cmd(cmd)
                    vlan_del.add(vlan_id)
                    vlan_add.add(1)

                tmp = dict_search('allowed_vlan_removed', interface_config)


                for vlan_id in (tmp or []):
                    cmd = f'bridge vlan del dev {interface} vid {vlan_id}'
                    self._cmd(cmd)
                    vlan_del.add(vlan_id)

                if 'native_vlan' in interface_config:
                    vlan_filter = 1
                    cmd = f'bridge vlan del dev {interface} vid 1'
                    self._cmd(cmd)
                    vlan_id = interface_config['native_vlan']
                    if int(vlan_id) != 1:
                        if 1 in vlan_add:
                            vlan_add.remove(1)
                        vlan_del.add(1)
                    cmd = f'bridge vlan add dev {interface} vid {vlan_id} pvid untagged master'
                    self._cmd(cmd)
                    vlan_add.add(vlan_id)
                    if vlan_id in vlan_del:
                        vlan_del.remove(vlan_id)

                if 'allowed_vlan' in interface_config:
                    vlan_filter = 1
                    if 'native_vlan' not in interface_config:
                        cmd = f'bridge vlan del dev {interface} vid 1'
                        self._cmd(cmd)
                        vlan_del.add(1)
                    for vlan in interface_config['allowed_vlan']:
                        cmd = f'bridge vlan add dev {interface} vid {vlan} master'
                        self._cmd(cmd)
                        vlan_add.add(vlan)
                        if vlan in vlan_del:
                            vlan_del.remove(vlan)

        for vlan in vlan_del:
            cmd = f'bridge vlan del dev {ifname} vid {vlan} self'
            self._cmd(cmd)

        for vlan in vlan_add:
            cmd = f'bridge vlan add dev {ifname} vid {vlan} self'
            self._cmd(cmd)

        # enable/disable Vlan Filter
        self.set_vlan_filter(vlan_filter)


        # Enable/Disable of an interface must always be done at the end of the
        # derived class to make use of the ref-counting set_admin_state()
        # function. We will only enable the interface if 'up' was called as
        # often as 'down'. This is required by some interface implementations
        # as certain parameters can only be changed when the interface is
        # in admin-down state. This ensures the link does not flap during
        # reconfiguration.
        state = 'down' if 'disable' in config else 'up'
        self.set_admin_state(state)
