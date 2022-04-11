# Copyright 2021-2022 VyOS maintainers and contributors <maintainers@vyos.io>
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

from vyos.util import popen

# These drivers do not support using ethtool to change the speed, duplex, or
# flow control settings
_drivers_without_speed_duplex_flow = ['vmxnet3', 'virtio_net', 'xen_netfront',
                                      'iavf', 'ice', 'i40e', 'hv_netvsc']

class Ethtool:
    """
    Class is used to retrive and cache information about an ethernet adapter
    """
    # dictionary containing driver featurs, it will be populated on demand and
    # the content will look like:
    # {
    #   'tls-hw-tx-offload': {'fixed': True, 'enabled': False},
    #   'tx-checksum-fcoe-crc': {'fixed': True, 'enabled': False},
    #   'tx-checksum-ip-generic': {'fixed': False, 'enabled': True},
    #   'tx-checksum-ipv4': {'fixed': True, 'enabled': False},
    #   'tx-checksum-ipv6': {'fixed': True, 'enabled': False},
    #   'tx-checksum-sctp': {'fixed': True, 'enabled': False},
    #   'tx-checksumming': {'fixed': False, 'enabled': True},
    #   'tx-esp-segmentation': {'fixed': True, 'enabled': False},
    # }
    _features = { }
    # dictionary containing available interface speed and duplex settings
    # {
    #   '10'  : {'full': '', 'half': ''},
    #   '100' : {'full': '', 'half': ''},
    #   '1000': {'full': ''}
    #  }
    _speed_duplex = {'auto': {'auto': ''}}
    _ring_buffers = { }
    _ring_buffers_max = { }
    _driver_name = None
    _auto_negotiation = False
    _flow_control = False
    _flow_control_enabled = None

    def __init__(self, ifname):
        # Get driver used for interface
        sysfs_file = f'/sys/class/net/{ifname}/device/driver/module'
        if os.path.exists(sysfs_file):
            link = os.readlink(sysfs_file)
            self._driver_name = os.path.basename(link)

        # Build a dictinary of supported link-speed and dupley settings.
        out, err = popen(f'ethtool {ifname}')
        reading = False
        pattern = re.compile(r'\d+base.*')
        for line in out.splitlines()[1:]:
            line = line.lstrip()
            if 'Supported link modes:' in line:
                reading = True
            if 'Supported pause frame use:' in line:
                reading = False
            if reading:
                for block in line.split():
                    if pattern.search(block):
                        speed = block.split('base')[0]
                        duplex = block.split('/')[-1].lower()
                        if speed not in self._speed_duplex:
                            self._speed_duplex.update({ speed : {}})
                        if duplex not in self._speed_duplex[speed]:
                            self._speed_duplex[speed].update({ duplex : ''})
            if 'Auto-negotiation:' in line:
                # Split the following string: Auto-negotiation: off
                # we are only interested in off or on
                tmp = line.split()[-1]
                self._auto_negotiation = bool(tmp == 'on')

        # Now populate features dictionaty
        out, err = popen(f'ethtool --show-features {ifname}')
        # skip the first line, it only says: "Features for eth0":
        for line in out.splitlines()[1:]:
            if ":" in line:
                key, value = [s.strip() for s in line.strip().split(":", 1)]
                fixed = bool('fixed' in value)
                if fixed:
                    value = value.split()[0].strip()
                self._features[key.strip()] = {
                    'enabled' : bool(value == 'on'),
                    'fixed' : fixed
                }

        out, err = popen(f'ethtool --show-ring {ifname}')
        # We are only interested in line 2-5 which contains the device maximum
        # ringbuffers
        for line in out.splitlines()[2:6]:
            if ':' in line:
                key, value = [s.strip() for s in line.strip().split(":", 1)]
                key = key.lower().replace(' ', '_')
                # T3645: ethtool version used on Debian Bullseye changed the
                # output format from 0 -> n/a. As we are only interested in the
                # tx/rx keys we do not care about RX Mini/Jumbo.
                if value.isdigit():
                    self._ring_buffers_max[key] = value
        # Now we wan't to get the current RX/TX ringbuffer values - used for
        for line in out.splitlines()[7:11]:
            if ':' in line:
                key, value = [s.strip() for s in line.strip().split(":", 1)]
                key = key.lower().replace(' ', '_')
                # T3645: ethtool version used on Debian Bullseye changed the
                # output format from 0 -> n/a. As we are only interested in the
                # tx/rx keys we do not care about RX Mini/Jumbo.
                if value.isdigit():
                    self._ring_buffers[key] = value

        # Get current flow control settings, but this is not supported by
        # all NICs (e.g. vmxnet3 does not support is)
        out, err = popen(f'ethtool --show-pause {ifname}')
        if len(out.splitlines()) > 1:
            self._flow_control = True
            # read current flow control setting, this returns:
            # ['Autonegotiate:', 'on']
            self._flow_control_enabled = out.splitlines()[1].split()[-1]

    def get_auto_negotiation(self):
        return self._auto_negotiation

    def get_driver_name(self):
        return self._driver_name

    def _get_generic(self, feature):
        """
        Generic method to read self._features and return a tuple for feature
        enabled and feature is fixed.

        In case of a missing key, return "fixed = True and enabled = False"
        """
        fixed = True
        enabled = False
        if feature in self._features:
            if 'enabled' in self._features[feature]:
                enabled = self._features[feature]['enabled']
            if 'fixed' in self._features[feature]:
                fixed = self._features[feature]['fixed']
        return enabled, fixed

    def get_generic_receive_offload(self):
        return self._get_generic('generic-receive-offload')

    def get_generic_segmentation_offload(self):
        return self._get_generic('generic-segmentation-offload')

    def get_large_receive_offload(self):
        return self._get_generic('large-receive-offload')

    def get_scatter_gather(self):
        return self._get_generic('scatter-gather')

    def get_tcp_segmentation_offload(self):
        return self._get_generic('tcp-segmentation-offload')

    def get_ring_buffer_max(self, rx_tx):
        # Configuration of RX/TX ring-buffers is not supported on every device,
        # thus when it's impossible return None
        if rx_tx not in ['rx', 'tx']:
            ValueError('Ring-buffer type must be either "rx" or "tx"')
        return self._ring_buffers_max.get(rx_tx, None)

    def get_ring_buffer(self, rx_tx):
        # Configuration of RX/TX ring-buffers is not supported on every device,
        # thus when it's impossible return None
        if rx_tx not in ['rx', 'tx']:
            ValueError('Ring-buffer type must be either "rx" or "tx"')
        return str(self._ring_buffers.get(rx_tx, None))

    def check_speed_duplex(self, speed, duplex):
        """ Check if the passed speed and duplex combination is supported by
        the underlaying network adapter. """
        if isinstance(speed, int):
            speed = str(speed)
        if speed != 'auto' and not speed.isdigit():
            raise ValueError(f'Value "{speed}" for speed is invalid!')
        if duplex not in ['auto', 'full', 'half']:
            raise ValueError(f'Value "{duplex}" for duplex is invalid!')

        if self.get_driver_name() in _drivers_without_speed_duplex_flow:
            return False

        if speed in self._speed_duplex:
            if duplex in self._speed_duplex[speed]:
                return True
        return False

    def check_flow_control(self):
        """ Check if the NIC supports flow-control """
        if self.get_driver_name() in _drivers_without_speed_duplex_flow:
            return False
        return self._flow_control

    def get_flow_control(self):
        if self._flow_control_enabled == None:
            raise ValueError('Interface does not support changing '\
                             'flow-control settings!')
        return self._flow_control_enabled
