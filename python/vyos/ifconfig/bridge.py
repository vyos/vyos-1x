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
from vyos.utils.assertion import assert_boolean
from vyos.utils.assertion import assert_list
from vyos.utils.assertion import assert_positive
from vyos.utils.dict import dict_search
from vyos.utils.network import interface_exists
from vyos.configdict import get_vlan_ids
from vyos.configdict import list_diff

@Interface.register
class BridgeIf(Interface):
    """
    A bridge is a way to connect two Ethernet segments together in a protocol
    independent way. Packets are forwarded based on Ethernet address, rather
    than IP address (like a router). Since forwarding is done at Layer 2, all
    protocols can go transparently through a bridge.

    The Linux bridge code implements a subset of the ANSI/IEEE 802.1d standard.
    """
    iftype = 'bridge'
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
        'vlan_protocol': {
            'validate': lambda v: assert_list(v, ['0x88a8', '0x8100']),
            'location': '/sys/class/net/{ifname}/bridge/vlan_protocol',
        },
        'multicast_querier': {
            'validate': assert_boolean,
            'location': '/sys/class/net/{ifname}/bridge/multicast_querier',
        },
        'multicast_snooping': {
            'validate': assert_boolean,
            'location': '/sys/class/net/{ifname}/bridge/multicast_snooping',
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

        # VLAN of bridge parent interface is always 1
        # VLAN 1 is the default VLAN for all unlabeled packets
        cmd = f'bridge vlan add dev {self.ifname} vid 1 pvid untagged self'
        self._cmd(cmd)

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

    def set_multicast_snooping(self, enable):
        """
        Enable or disable multicast snooping on the bridge.

        Use enable=1 to enable or enable=0 to disable

        Example:
        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').set_multicast_snooping(1)
        """
        self.set_interface('multicast_snooping', enable)

    def add_port(self, interface):
        """
        Add physical interface to bridge (member port)

        Example:
        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').add_port('eth0')
        >>> BridgeIf('br0').add_port('eth1')
        """
        # Bridge port handling of wireless interfaces is done by hostapd.
        if 'wlan' in interface:
            return

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

    def set_vlan_protocol(self, protocol):
        """
        Set protocol used for VLAN filtering.
        The valid values are 0x8100(802.1q) or 0x88A8(802.1ad).

        Example:
        >>> from vyos.ifconfig import Interface
        >>> BridgeIf('br0').del_port('eth1')
        """

        if protocol not in ['802.1q', '802.1ad']:
            raise ValueError()

        map = {
            '802.1ad': '0x88a8',
            '802.1q' : '0x8100'
        }

        return self.set_interface('vlan_protocol', map[protocol])

    def update(self, config):
        """ General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface. """

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

        # enable or disable multicast snooping
        tmp = dict_search('igmp.snooping', config)
        value = '1' if (tmp != None) else '0'
        self.set_multicast_snooping(value)

        # enable or disable IGMP querier
        tmp = dict_search('igmp.querier', config)
        value = '1' if (tmp != None) else '0'
        self.set_multicast_querier(value)

        # remove interface from bridge
        tmp = dict_search('member.interface_remove', config)
        for member in (tmp or []):
            if interface_exists(member):
                self.del_port(member)

        # enable/disable VLAN Filter
        tmp = '1' if 'enable_vlan' in config else '0'
        self.set_vlan_filter(tmp)

        tmp = config.get('protocol')
        self.set_vlan_protocol(tmp)

        # add VLAN interfaces to local 'parent' bridge to allow forwarding
        if 'enable_vlan' in config:
            for vlan in config.get('vif_remove', {}):
                # Remove old VLANs from the bridge
                cmd = f'bridge vlan del dev {self.ifname} vid {vlan} self'
                self._cmd(cmd)

            for vlan in config.get('vif', {}):
                cmd = f'bridge vlan add dev {self.ifname} vid {vlan} self'
                self._cmd(cmd)

            # VLAN of bridge parent interface is always 1. VLAN 1 is the default
            # VLAN for all unlabeled packets
            cmd = f'bridge vlan add dev {self.ifname} vid 1 pvid untagged self'
            self._cmd(cmd)

        tmp = dict_search('member.interface', config)
        if tmp:
            for interface, interface_config in tmp.items():
                # if interface does yet not exist bail out early and
                # add it later
                if not interface_exists(interface):
                    continue

                # Bridge lower "physical" interface
                lower = Interface(interface)

                # If we've come that far we already verified the interface does
                # not have any addresses configured by CLI so just flush any
                # remaining ones
                lower.flush_addrs()

                # enslave interface port to bridge
                self.add_port(interface)

                if not interface.startswith('wlan'):
                    # always set private-vlan/port isolation - this can not be
                    # done when lower link is a wifi link, as it will trigger:
                    # RTNETLINK answers: Operation not supported
                    tmp = dict_search('isolated', interface_config)
                    value = 'on' if (tmp != None) else 'off'
                    lower.set_port_isolation(value)

                # set bridge port path cost
                if 'cost' in interface_config:
                    lower.set_path_cost(interface_config['cost'])

                # set bridge port path priority
                if 'priority' in interface_config:
                    lower.set_path_priority(interface_config['priority'])

                if 'enable_vlan' in config:
                    add_vlan = []
                    native_vlan_id = None
                    allowed_vlan_ids= []
                    cur_vlan_ids = get_vlan_ids(interface)

                    if 'native_vlan' in interface_config:
                        vlan_id = interface_config['native_vlan']
                        add_vlan.append(vlan_id)
                        native_vlan_id = vlan_id

                    if 'allowed_vlan' in interface_config:
                        for vlan in interface_config['allowed_vlan']:
                            vlan_range = vlan.split('-')
                            if len(vlan_range) == 2:
                                for vlan_add in range(int(vlan_range[0]),int(vlan_range[1]) + 1):
                                    add_vlan.append(str(vlan_add))
                                    allowed_vlan_ids.append(str(vlan_add))
                            else:
                                add_vlan.append(vlan)
                                allowed_vlan_ids.append(vlan)

                    # Remove redundant VLANs from the system
                    for vlan in list_diff(cur_vlan_ids, add_vlan):
                        cmd = f'bridge vlan del dev {interface} vid {vlan} master'
                        self._cmd(cmd)

                    for vlan in allowed_vlan_ids:
                        cmd = f'bridge vlan add dev {interface} vid {vlan} master'
                        self._cmd(cmd)

                    # Setting native VLAN to system
                    if native_vlan_id:
                        cmd = f'bridge vlan add dev {interface} vid {native_vlan_id} pvid untagged master'
                        self._cmd(cmd)

        super().update(config)
