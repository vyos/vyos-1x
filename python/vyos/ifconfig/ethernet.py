# Copyright 2019-2023 VyOS maintainers and contributors <maintainers@vyos.io>
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

from glob import glob

from vyos.base import Warning
from vyos.ethtool import Ethtool
from vyos.ifconfig import Section
from vyos.ifconfig.interface import Interface
from vyos.utils.dict import dict_search
from vyos.utils.file import read_file
from vyos.utils.process import run
from vyos.utils.assertion import assert_list

@Interface.register
class EthernetIf(Interface):
    """
    Abstraction of a Linux Ethernet Interface
    """
    iftype = 'ethernet'
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
        run(f'ethtool --features {ifname} {option} {value}')
        return False

    _command_set = {**Interface._command_set, **{
        'gro': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'possible': lambda i, v: EthernetIf.feature(i, 'gro', v),
        },
        'gso': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'possible': lambda i, v: EthernetIf.feature(i, 'gso', v),
        },
        'hw-tc-offload': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'possible': lambda i, v: EthernetIf.feature(i, 'hw-tc-offload', v),
        },
        'lro': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'possible': lambda i, v: EthernetIf.feature(i, 'lro', v),
        },
        'sg': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'possible': lambda i, v: EthernetIf.feature(i, 'sg', v),
        },
        'tso': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'possible': lambda i, v: EthernetIf.feature(i, 'tso', v),
        },
    }}

    @staticmethod
    def get_bond_member_allowed_options() -> list:
        """
        Return list of options which are allowed for changing,
        when interface is a bond member
        :return: List of interface options
        :rtype: list
        """
        bond_allowed_sections = [
            'description',
            'disable',
            'disable_flow_control',
            'disable_link_detect',
            'duplex',
            'eapol.ca_certificate',
            'eapol.certificate',
            'eapol.passphrase',
            'mirror.egress',
            'mirror.ingress',
            'offload.gro',
            'offload.gso',
            'offload.lro',
            'offload.rfs',
            'offload.rps',
            'offload.sg',
            'offload.tso',
            'redirect',
            'ring_buffer.rx',
            'ring_buffer.tx',
            'speed',
            'hw_id'
        ]
        return bond_allowed_sections

    def __init__(self, ifname, **kargs):
        super().__init__(ifname, **kargs)
        self.ethtool = Ethtool(ifname)

    def remove(self):
        """
        Remove interface from config. Removing the interface deconfigures all
        assigned IP addresses.
        Example:
        >>> from vyos.ifconfig import WWANIf
        >>> i = EthernetIf('eth0')
        >>> i.remove()
        """

        if self.exists(self.ifname):
            # interface is placed in A/D state when removed from config! It
            # will remain visible for the operating system.
            self.set_admin_state('down')

        # Remove all VLAN subinterfaces - filter with the VLAN dot
        for vlan in [x for x in Section.interfaces(self.iftype) if x.startswith(f'{self.ifname}.')]:
            Interface(vlan).remove()

        super().remove()

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

        if not self.ethtool.check_flow_control():
            self._debug_msg(f'NIC driver does not support changing flow control settings!')
            return False

        current = self.ethtool.get_flow_control()
        if current != enable:
            # Assemble command executed on system. Unfortunately there is no way
            # to change this setting via sysfs
            cmd = f'ethtool --pause {ifname} autoneg {enable} tx {enable} rx {enable}'
            output, code = self._popen(cmd)
            if code:
                Warning(f'could not change "{ifname}" flow control setting!')
            return output
        return None

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
        ifname = self.config['ifname']

        if speed not in ['auto', '10', '100', '1000', '2500', '5000', '10000',
                         '25000', '40000', '50000', '100000', '400000']:
            raise ValueError("Value out of range (speed)")

        if duplex not in ['auto', 'full', 'half']:
            raise ValueError("Value out of range (duplex)")

        if not self.ethtool.check_speed_duplex(speed, duplex):
            Warning(f'changing speed/duplex setting on "{ifname}" is unsupported!')
            return

        if not self.ethtool.check_auto_negotiation_supported():
            Warning(f'changing auto-negotiation setting on "{ifname}" is unsupported!')
            return

        # Get current speed and duplex settings:
        ifname = self.config['ifname']
        if self.ethtool.get_auto_negotiation():
            if speed == 'auto' and duplex == 'auto':
                # bail out early as nothing is to change
                return
        else:
            # XXX: read in current speed and duplex settings
            # There are some "nice" NICs like AX88179 which do not support
            # reading the speed thus we simply fallback to the supplied speed
            # to not cause any change here and raise an exception.
            cur_speed = read_file(f'/sys/class/net/{ifname}/speed', speed)
            cur_duplex = read_file(f'/sys/class/net/{ifname}/duplex', duplex)
            if (cur_speed == speed) and (cur_duplex == duplex):
                # bail out early as nothing is to change
                return

        cmd = f'ethtool --change {ifname}'
        try:
            if speed == 'auto' or duplex == 'auto':
                cmd += ' autoneg on'
            else:
                cmd += f' speed {speed} duplex {duplex} autoneg off'
            return self._cmd(cmd)
        except PermissionError:
            # Some NICs do not tell that they don't suppport settings speed/duplex,
            # but they do not actually support it either.
            # In that case it's probably better to ignore the error
            # than end up with a broken config.
            print('Warning: could not set speed/duplex settings: operation not permitted!')

    def set_gro(self, state):
        """
        Enable Generic Receive Offload. State can be either True or False.

        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_gro(True)
        """
        if not isinstance(state, bool):
            raise ValueError('Value out of range')

        enabled, fixed = self.ethtool.get_generic_receive_offload()
        if enabled != state:
            if not fixed:
                return self.set_interface('gro', 'on' if state else 'off')
            else:
                print('Adapter does not support changing generic-receive-offload settings!')
        return False

    def set_gso(self, state):
        """
        Enable Generic Segmentation offload. State can be either True or False.
        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_gso(True)
        """
        if not isinstance(state, bool):
            raise ValueError('Value out of range')

        enabled, fixed = self.ethtool.get_generic_segmentation_offload()
        if enabled != state:
            if not fixed:
                return self.set_interface('gso', 'on' if state else 'off')
            else:
                print('Adapter does not support changing generic-segmentation-offload settings!')
        return False

    def set_hw_tc_offload(self, state):
        """
        Enable hardware TC flow offload. State can be either True or False.
        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_hw_tc_offload(True)
        """
        if not isinstance(state, bool):
            raise ValueError('Value out of range')

        enabled, fixed = self.ethtool.get_hw_tc_offload()
        if enabled != state:
            if not fixed:
                return self.set_interface('hw-tc-offload', 'on' if state else 'off')
            else:
                print('Adapter does not support changing hw-tc-offload settings!')
        return False

    def set_lro(self, state):
        """
        Enable Large Receive offload. State can be either True or False.
        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_lro(True)
        """
        if not isinstance(state, bool):
            raise ValueError('Value out of range')

        enabled, fixed = self.ethtool.get_large_receive_offload()
        if enabled != state:
            if not fixed:
                return self.set_interface('lro', 'on' if state else 'off')
            else:
                print('Adapter does not support changing large-receive-offload settings!')
        return False

    def set_rps(self, state):
        if not isinstance(state, bool):
            raise ValueError('Value out of range')

        rps_cpus = 0
        queues = len(glob(f'/sys/class/net/{self.ifname}/queues/rx-*'))
        if state:
            # Enable RPS on all available CPUs except CPU0 which we will not
            # utilize so the system has one spare core when it's under high
            # preasure to server other means. Linux sysfs excepts a bitmask
            # representation of the CPUs which should participate on RPS, we
            # can enable more CPUs that are physically present on the system,
            # Linux will clip that internally!
            rps_cpus = (1 << os.cpu_count()) -1

            # XXX: we should probably reserve one core when the system is under
            # high preasure so we can still have a core left for housekeeping.
            # This is done by masking out the lowst bit so CPU0 is spared from
            # receive packet steering.
            rps_cpus &= ~1

        for i in range(0, queues):
            self._write_sysfs(f'/sys/class/net/{self.ifname}/queues/rx-{i}/rps_cpus', f'{rps_cpus:x}')

        # send bitmask representation as hex string without leading '0x'
        return True

    def set_rfs(self, state):
        rfs_flow = 0
        queues = len(glob(f'/sys/class/net/{self.ifname}/queues/rx-*'))
        if state:
            global_rfs_flow = 32768
            rfs_flow = int(global_rfs_flow/queues)

        for i in range(0, queues):
            self._write_sysfs(f'/sys/class/net/{self.ifname}/queues/rx-{i}/rps_flow_cnt', rfs_flow)

        return True

    def set_sg(self, state):
        """
        Enable Scatter-Gather support. State can be either True or False.

        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_sg(True)
        """
        if not isinstance(state, bool):
            raise ValueError('Value out of range')

        enabled, fixed = self.ethtool.get_scatter_gather()
        if enabled != state:
            if not fixed:
                return self.set_interface('sg', 'on' if state else 'off')
            else:
                print('Adapter does not support changing scatter-gather settings!')
        return False

    def set_tso(self, state):
        """
        Enable TCP segmentation offloading. State can be either True or False.

        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_tso(False)
        """
        if not isinstance(state, bool):
            raise ValueError('Value out of range')

        enabled, fixed = self.ethtool.get_tcp_segmentation_offload()
        if enabled != state:
            if not fixed:
                return self.set_interface('tso', 'on' if state else 'off')
            else:
                print('Adapter does not support changing tcp-segmentation-offload settings!')
        return False

    def set_ring_buffer(self, rx_tx, size):
        """
        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_ring_buffer('rx', '4096')
        """
        current_size = self.ethtool.get_ring_buffer(rx_tx)
        if current_size == size:
            # bail out early if nothing is about to change
            return None

        ifname = self.config['ifname']
        cmd = f'ethtool --set-ring {ifname} {rx_tx} {size}'
        output, code = self._popen(cmd)
        # ethtool error codes:
        #  80 - value already setted
        #  81 - does not possible to set value
        if code and code != 80:
            print(f'could not set "{rx_tx}" ring-buffer for {ifname}')
        return output

    def update(self, config):
        """ General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface. """

        # disable ethernet flow control (pause frames)
        value = 'off' if 'disable_flow_control' in config else 'on'
        self.set_flow_control(value)

        # GRO (generic receive offload)
        self.set_gro(dict_search('offload.gro', config) != None)

        # GSO (generic segmentation offload)
        self.set_gso(dict_search('offload.gso', config) != None)

        # GSO (generic segmentation offload)
        self.set_hw_tc_offload(dict_search('offload.hw_tc_offload', config) != None)

        # LRO (large receive offload)
        self.set_lro(dict_search('offload.lro', config) != None)

        # RPS - Receive Packet Steering
        self.set_rps(dict_search('offload.rps', config) != None)

        # RFS - Receive Flow Steering
        self.set_rfs(dict_search('offload.rfs', config) != None)

        # scatter-gather option
        self.set_sg(dict_search('offload.sg', config) != None)

        # TSO (TCP segmentation offloading)
        self.set_tso(dict_search('offload.tso', config) != None)

        # Set physical interface speed and duplex
        if 'speed_duplex_changed' in config:
            if {'speed', 'duplex'} <= set(config):
                speed = config.get('speed')
                duplex = config.get('duplex')
                self.set_speed_duplex(speed, duplex)

        # Set interface ring buffer
        if 'ring_buffer' in config:
            for rx_tx, size in config['ring_buffer'].items():
                self.set_ring_buffer(rx_tx, size)

        # call base class last
        super().update(config)
