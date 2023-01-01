# Copyright 2022 VyOS maintainers and contributors <maintainers@vyos.io>
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

from vyos.qos.base import QoSBase

class RandomDetect(QoSBase):
    _parent = 1

    # https://man7.org/linux/man-pages/man8/tc.8.html
    def update(self, config, direction):

        tmp = f'tc qdisc add dev {self._interface} root handle {self._parent}:0 dsmark indices 8 set_tc_index'
        self._cmd(tmp)

        tmp = f'tc filter add dev {self._interface} parent {self._parent}:0 protocol ip prio 1 tcindex mask 0xe0 shift 5'
        self._cmd(tmp)

        # Generalized Random Early Detection
        handle = self._parent +1
        tmp = f'tc qdisc add dev {self._interface} parent {self._parent}:0 handle {handle}:0 gred setup DPs 8 default 0 grio'
        self._cmd(tmp)

        bandwidth = self._rate_convert(config['bandwidth'])

        # set VQ (virtual queue) parameters
        for precedence, precedence_config in config['precedence'].items():
            precedence = int(precedence)
            avg_pkt = int(precedence_config['average_packet'])
            limit = int(precedence_config['queue_limit']) * avg_pkt
            min_val = int(precedence_config['minimum_threshold']) * avg_pkt
            max_val = int(precedence_config['maximum_threshold']) * avg_pkt

            tmp  = f'tc qdisc change dev {self._interface} handle {handle}:0 gred limit {limit} min {min_val} max {max_val} avpkt {avg_pkt} '

            burst = (2 * int(precedence_config['minimum_threshold']) + int(precedence_config['maximum_threshold'])) // 3
            probability = 1 / int(precedence_config['mark_probability'])
            tmp += f'burst {burst} bandwidth {bandwidth} probability {probability} DP {precedence} prio {8 - precedence:x}'

            self._cmd(tmp)

        # call base class
        super().update(config, direction)
