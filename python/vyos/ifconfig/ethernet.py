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
from vyos.ifconfig.vlan import VLAN

from vyos.validate import *


@Interface.register
@VLAN.enable
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
        }
    }


    _command_set = {**Interface._command_set, **{
        'gro': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'shellcmd': '/sbin/ethtool -K {ifname} gro {value}',
        },
        'gso': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'shellcmd': '/sbin/ethtool -K {ifname} gso {value}',
        },
        'sg': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'shellcmd': '/sbin/ethtool -K {ifname} sg {value}',
        },
        'tso': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'shellcmd': '/sbin/ethtool -K {ifname} tso {value}',
        },
        'ufo': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'shellcmd': '/sbin/ethtool -K {ifname} ufo {value}',
        },
    }}

    def _delete(self):
        # Ethernet interfaces can not be removed
        pass

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
        if state not in ['on', 'off']:
            raise ValueError('state must be "on" or "off"')

        cmd = '/sbin/ethtool -K {} ufo {}'.format(self.config['ifname'], state)
        return self._cmd(cmd)
