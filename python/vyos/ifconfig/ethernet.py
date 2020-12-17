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

import os
import re

from vyos.ifconfig.interface import Interface
from vyos.validate import assert_list
from vyos.util import run
from vyos.util import dict_search

@Interface.register
class EthernetIf(Interface):
    """
    Abstraction of a Linux Ethernet Interface
    """

    default = {
        'type': 'ethernet',
    }
    definition = {
        **Interface.definition,
        **{
            'section': 'ethernet',
            'prefixes': ['lan', 'eth', 'eno', 'ens', 'enp', 'enx'],
            'bondable': True,
            'broadcast': True,
            'bridgeable': True,
            'eternal': '(lan|eth|eno|ens|enp|enx)[0-9]+$',
        }
    }

    @staticmethod
    def feature(ifname, option, value):
        run(f'/sbin/ethtool -K {ifname} {option} {value}','ifconfig')
        return False

    _command_set = {**Interface._command_set, **{
        'gro': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'possible': lambda i, v: EthernetIf.feature(i, 'gro', v),
            # 'shellcmd': '/sbin/ethtool -K {ifname} gro {value}',
        },
        'gso': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'possible': lambda i, v: EthernetIf.feature(i, 'gso', v),
            # 'shellcmd': '/sbin/ethtool -K {ifname} gso {value}',
        },
        'sg': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'possible': lambda i, v: EthernetIf.feature(i, 'sg', v),
            # 'shellcmd': '/sbin/ethtool -K {ifname} sg {value}',
        },
        'tso': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'possible': lambda i, v: EthernetIf.feature(i, 'tso', v),
            # 'shellcmd': '/sbin/ethtool -K {ifname} tso {value}',
        },
        'ufo': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'possible': lambda i, v: EthernetIf.feature(i, 'ufo', v),
            # 'shellcmd': '/sbin/ethtool -K {ifname} ufo {value}',
        },
    }}

    def get_driver_name(self):
        """
        Return the driver name used by NIC. Some NICs don't support all
        features e.g. changing link-speed, duplex

        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.get_driver_name()
        'vmxnet3'
        """
        sysfs_file = '/sys/class/net/{}/device/driver/module'.format(
            self.config['ifname'])
        if os.path.exists(sysfs_file):
            link = os.readlink(sysfs_file)
            return os.path.basename(link)
        else:
            return None

    def set_flow_control(self, enable):
        """
        Changes the pause parameters of the specified Ethernet device.

        @param enable: true -> enable pause frames, false -> disable pause frames

        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_flow_control(True)
        """
        ifname = self.config['ifname']

        if enable not in ['on', 'off']:
            raise ValueError("Value out of range")

        if self.get_driver_name() in ['vmxnet3', 'virtio_net', 'xen_netfront']:
            self._debug_msg('{} driver does not support changing flow control settings!'
                            .format(self.get_driver_name()))
            return

        # Get current flow control settings:
        cmd = f'/sbin/ethtool --show-pause {ifname}'
        output, code = self._popen(cmd)
        if code == 76:
            # the interface does not support it
            return ''
        if code:
            # never fail here as it prevent vyos to boot
            print(f'unexpected return code {code} from {cmd}')
            return ''

        # The above command returns - with tabs:
        #
        # Pause parameters for eth0:
        # Autonegotiate:  on
        # RX:             off
        # TX:             off
        if re.search("Autonegotiate:\ton", output):
            if enable == "on":
                # flowcontrol is already enabled - no need to re-enable it again
                # this will prevent the interface from flapping as applying the
                # flow-control settings will take the interface down and bring
                # it back up every time.
                return ''

        # Assemble command executed on system. Unfortunately there is no way
        # to change this setting via sysfs
        cmd = f'/sbin/ethtool --pause {ifname} autoneg {enable} tx {enable} rx {enable}'
        output, code = self._popen(cmd)
        if code:
            print(f'could not set flowcontrol for {ifname}')
        return output

    def set_speed_duplex(self, speed, duplex):
        """
        Set link speed in Mbit/s and duplex.

        @speed can be any link speed in MBit/s, e.g. 10, 100, 1000 auto
        @duplex can be half, full, auto

        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_speed_duplex('auto', 'auto')
        """

        if speed not in ['auto', '10', '100', '1000', '2500', '5000', '10000', '25000', '40000', '50000', '100000', '400000']:
            raise ValueError("Value out of range (speed)")

        if duplex not in ['auto', 'full', 'half']:
            raise ValueError("Value out of range (duplex)")

        if self.get_driver_name() in ['vmxnet3', 'virtio_net', 'xen_netfront']:
            self._debug_msg('{} driver does not support changing speed/duplex settings!'
                            .format(self.get_driver_name()))
            return

        # Get current speed and duplex settings:
        cmd = '/sbin/ethtool {0}'.format(self.config['ifname'])
        tmp = self._cmd(cmd)

        if re.search("\tAuto-negotiation: on", tmp):
            if speed == 'auto' and duplex == 'auto':
                # bail out early as nothing is to change
                return
        else:
            # read in current speed and duplex settings
            cur_speed = 0
            cur_duplex = ''
            for line in tmp.splitlines():
                if line.lstrip().startswith("Speed:"):
                    non_decimal = re.compile(r'[^\d.]+')
                    cur_speed = non_decimal.sub('', line)
                    continue

                if line.lstrip().startswith("Duplex:"):
                    cur_duplex = line.split()[-1].lower()
                    break

            if (cur_speed == speed) and (cur_duplex == duplex):
                # bail out early as nothing is to change
                return

        cmd = '/sbin/ethtool -s {}'.format(self.config['ifname'])
        if speed == 'auto' or duplex == 'auto':
            cmd += ' autoneg on'
        else:
            cmd += ' speed {} duplex {} autoneg off'.format(speed, duplex)

        return self._cmd(cmd)

    def set_gro(self, state):
        """
        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_gro('on')
        """
        return self.set_interface('gro', state)

    def set_gso(self, state):
        """
        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_gso('on')
        """
        return self.set_interface('gso', state)

    def set_sg(self, state):
        """
        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_sg('on')
        """
        return self.set_interface('sg', state)

    def set_tso(self, state):
        """
        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_tso('on')
        """
        return self.set_interface('tso', state)

    def set_ufo(self, state):
        """
        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_udp_offload('on')
        """
        return self.set_interface('ufo', state)

    def set_xdp(self, enabled):
        """
        """
        ifname = self.config['ifname']
        cmd = f'ip link set dev {ifname} xdp off'
        if enabled:
            # use 'xdpgeneric' for the time beeing until we can detect supported
            # drivers or have a lookup table of whatever kind. This then can be
            # replaced by xdpdrv
            cmd = f'ip -force link set dev {ifname} xdpgeneric obj /usr/share/vyos/ebpf/xdp_router.o'
        try:
            return self._cmd(cmd)
        except:
            from vyos import ConfigError
            raise ConfigError('Error: Device does not allow enslaving to a bridge.')


    def set_ring_buffer(self, b_type, b_size):
        """
        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_ring_buffer('rx', '4096')
        """
        cmd = '/sbin/ethtool -G {0} {1} {2}'.format(self.config['ifname'], b_type, b_size)
        output, code = self._popen(cmd)
        # ethtool error codes:
        #  80 - value already setted
        #  81 - does not possible to set value
        if code and code != 80:
            print('could not set {0} ring-buffer for {1}'.format(b_type, self.config['ifname']))
        return output


    def update(self, config):
        """ General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface. """

        # call base class first
        super().update(config)

        # disable ethernet flow control (pause frames)
        value = 'off' if 'disable_flow_control' in config.keys() else 'on'
        self.set_flow_control(value)

        # GRO (generic receive offload)
        tmp = dict_search('offload_options.generic_receive', config)
        value = tmp if (tmp != None) else 'off'
        self.set_gro(value)

        # GSO (generic segmentation offload)
        tmp = dict_search('offload_options.generic_segmentation', config)
        value = tmp if (tmp != None) else 'off'
        self.set_gso(value)

        # scatter-gather option
        tmp = dict_search('offload_options.scatter_gather', config)
        value = tmp if (tmp != None) else 'off'
        self.set_sg(value)

        # TSO (TCP segmentation offloading)
        tmp = dict_search('offload_options.udp_fragmentation', config)
        value = tmp if (tmp != None) else 'off'
        self.set_tso(value)

        # UDP fragmentation offloading
        tmp = dict_search('offload_options.udp_fragmentation', config)
        value = tmp if (tmp != None) else 'off'
        self.set_ufo(value)

        # UDP fragmentation offloading
        tmp = dict_search('offload_options.xdp', config)
        self.set_xdp(tmp != None) # enable or disable

        # Set physical interface speed and duplex
        if {'speed', 'duplex'} <= set(config):
            speed = config.get('speed')
            duplex = config.get('duplex')
            self.set_speed_duplex(speed, duplex)

        # Set interface ring buffer
        if 'ring_buffer' in config:
            for b_type in config['ring_buffer']:
                self.set_ring_buffer(b_type, config['ring_buffer'][b_type])

        # Enable/Disable of an interface must always be done at the end of the
        # derived class to make use of the ref-counting set_admin_state()
        # function. We will only enable the interface if 'up' was called as
        # often as 'down'. This is required by some interface implementations
        # as certain parameters can only be changed when the interface is
        # in admin-down state. This ensures the link does not flap during
        # reconfiguration.
        state = 'down' if 'disable' in config else 'up'
        self.set_admin_state(state)
