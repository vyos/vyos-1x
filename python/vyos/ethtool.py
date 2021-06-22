# Copyright 2021 VyOS maintainers and contributors <maintainers@vyos.io>
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

from vyos.util import popen

class Ethtool:
    """
    Class is used to retrive and cache information about an ethernet adapter
    """

    # dictionary containing driver featurs, it will be populated on demand and
    # the content will look like:
    # {
    #   'tls-hw-tx-offload': {'fixed': True, 'on': False},
    #   'tx-checksum-fcoe-crc': {'fixed': True, 'on': False},
    #   'tx-checksum-ip-generic': {'fixed': False, 'on': True},
    #   'tx-checksum-ipv4': {'fixed': True, 'on': False},
    #   'tx-checksum-ipv6': {'fixed': True, 'on': False},
    #   'tx-checksum-sctp': {'fixed': True, 'on': False},
    #   'tx-checksumming': {'fixed': False, 'on': True},
    #   'tx-esp-segmentation': {'fixed': True, 'on': False},
    # }
    features = { }
    ring_buffers = { }

    def __init__(self, ifname):
        # Now populate features dictionaty
        out, err = popen(f'ethtool -k {ifname}')
        # skip the first line, it only says: "Features for eth0":
        for line in out.splitlines()[1:]:
            if ":" in line:
                key, value = [s.strip() for s in line.strip().split(":", 1)]
                fixed = "fixed" in value
                if fixed:
                    value = value.split()[0].strip()
                self.features[key.strip()] = {
                    "on": value == "on",
                    "fixed": fixed
                }

        out, err = popen(f'ethtool -g {ifname}')
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
                    self.ring_buffers[key] = int(value)


    def is_fixed_lro(self):
        # in case of a missing configuration, rather return "fixed". In Ethtool
        # terminology "fixed" means the setting can not be changed by the user.
        return self.features.get('large-receive-offload', True).get('fixed', True)

    def is_fixed_gro(self):
        # in case of a missing configuration, rather return "fixed". In Ethtool
        # terminology "fixed" means the setting can not be changed by the user.
        return self.features.get('generic-receive-offload', True).get('fixed', True)

    def is_fixed_gso(self):
        # in case of a missing configuration, rather return "fixed". In Ethtool
        # terminology "fixed" means the setting can not be changed by the user.
        return self.features.get('generic-segmentation-offload', True).get('fixed', True)

    def is_fixed_sg(self):
        # in case of a missing configuration, rather return "fixed". In Ethtool
        # terminology "fixed" means the setting can not be changed by the user.
        return self.features.get('scatter-gather', True).get('fixed', True)

    def is_fixed_tso(self):
        # in case of a missing configuration, rather return "fixed". In Ethtool
        # terminology "fixed" means the setting can not be changed by the user.
        return self.features.get('tcp-segmentation-offload', True).get('fixed', True)

    def is_fixed_ufo(self):
        # in case of a missing configuration, rather return "fixed". In Ethtool
        # terminology "fixed" means the setting can not be changed by the user.
        return self.features.get('udp-fragmentation-offload', True).get('fixed', True)

    def get_rx_buffer(self):
        # Configuration of RX ring-buffers is not supported on every device,
        # thus when it's impossible return None
        return self.ring_buffers.get('rx', None)

    def get_tx_buffer(self):
        # Configuration of TX ring-buffers is not supported on every device,
        # thus when it's impossible return None
        return self.ring_buffers.get('tx', None)
