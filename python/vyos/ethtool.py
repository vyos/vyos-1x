# Copyright 2021-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

import re

from json import loads
from vyos.utils.process import popen

# These drivers do not support using ethtool to change the speed, duplex, or
# flow control settings
_drivers_without_speed_duplex_flow = ['vmxnet3', 'virtio_net', 'xen_netfront',
                                      'iavf', 'ice', 'i40e', 'hv_netvsc', 'veth', 'ixgbevf',
                                      'tun']

class Ethtool:
    """
    Class is used to retrive and cache information about an ethernet adapter
    """
    # dictionary containing driver featurs, it will be populated on demand and
    # the content will look like:
    # [{'esp-hw-offload': {'active': False, 'fixed': True, 'requested': False},
    #   'esp-tx-csum-hw-offload': {'active': False,
    #                              'fixed': True,
    #                              'requested': False},
    #   'fcoe-mtu': {'active': False, 'fixed': True, 'requested': False},
    #   'generic-receive-offload': {'active': True,
    #                               'fixed': False,
    #                               'requested': True},
    #   'generic-segmentation-offload': {'active': True,
    #                                    'fixed': False,
    #                                    'requested': True},
    #   'highdma': {'active': True, 'fixed': False, 'requested': True},
    #   'ifname': 'eth0',
    #   'l2-fwd-offload': {'active': False, 'fixed': True, 'requested': False},
    #   'large-receive-offload': {'active': False,
    #                             'fixed': False,
    #                             'requested': False},
    # ...
    _features = { }
    # dictionary containing available interface speed and duplex settings
    # {
    #   '10'  : {'full': '', 'half': ''},
    #   '100' : {'full': '', 'half': ''},
    #   '1000': {'full': ''}
    #  }
    _speed_duplex = {'auto': {'auto': ''}}
    _ring_buffer = None
    _driver_name = None
    _auto_negotiation = False
    _auto_negotiation_supported = None
    _flow_control = None

    def __init__(self, ifname):
        # Get driver used for interface
        out, _ = popen(f'ethtool --driver {ifname}')
        driver = re.search(r'driver:\s(\w+)', out)
        if driver:
            self._driver_name = driver.group(1)

        # Build a dictinary of supported link-speed and dupley settings.
        out, _ = popen(f'ethtool {ifname}')
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
            if 'Supports auto-negotiation:' in line:
                # Split the following string: Auto-negotiation: off
                # we are only interested in off or on
                tmp = line.split()[-1]
                self._auto_negotiation_supported = bool(tmp == 'Yes')
            # Only read in if Auto-negotiation is supported
            if self._auto_negotiation_supported and 'Auto-negotiation:' in line:
                # Split the following string: Auto-negotiation: off
                # we are only interested in off or on
                tmp = line.split()[-1]
                self._auto_negotiation = bool(tmp == 'on')

        # Now populate driver features
        out, _ = popen(f'ethtool --json --show-features {ifname}')
        self._features = loads(out)

        # Get information about NIC ring buffers
        out, _ = popen(f'ethtool --json --show-ring {ifname}')
        self._ring_buffer = loads(out)

        # Get current flow control settings, but this is not supported by
        # all NICs (e.g. vmxnet3 does not support is)
        out, err = popen(f'ethtool --json --show-pause {ifname}')
        if not bool(err):
            self._flow_control = loads(out)

    def check_auto_negotiation_supported(self):
        """ Check if the NIC supports changing auto-negotiation """
        return self._auto_negotiation_supported

    def get_auto_negotiation(self):
        return self._auto_negotiation_supported and self._auto_negotiation

    def get_driver_name(self):
        return self._driver_name

    def _get_generic(self, feature):
        """
        Generic method to read self._features and return a tuple for feature
        enabled and feature is fixed.

        In case of a missing key, return "fixed = True and enabled = False"
        """
        active = False
        fixed = True
        if feature in self._features[0]:
            active = bool(self._features[0][feature]['active'])
            fixed = bool(self._features[0][feature]['fixed'])
        return active, fixed

    def get_generic_receive_offload(self):
        return self._get_generic('generic-receive-offload')

    def get_generic_segmentation_offload(self):
        return self._get_generic('generic-segmentation-offload')

    def get_hw_tc_offload(self):
        return self._get_generic('hw-tc-offload')

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
        return str(self._ring_buffer[0].get(f'{rx_tx}-max', None))

    def get_ring_buffer(self, rx_tx):
        # Configuration of RX/TX ring-buffers is not supported on every device,
        # thus when it's impossible return None
        if rx_tx not in ['rx', 'tx']:
            ValueError('Ring-buffer type must be either "rx" or "tx"')
        return str(self._ring_buffer[0].get(rx_tx, None))

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
        return bool(self._flow_control)

    def get_flow_control(self):
        if self._flow_control == None:
            raise ValueError('Interface does not support changing '\
                             'flow-control settings!')

        return 'on' if bool(self._flow_control[0]['autonegotiate']) else 'off'
