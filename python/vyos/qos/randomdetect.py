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

        # # Generalized Random Early Detection
        handle = self._parent
        tmp = f'tc qdisc add dev {self._interface} root handle {self._parent}:0 gred setup DPs 8 default 0 grio'
        self._cmd(tmp)
        bandwidth = self._rate_convert(config['bandwidth'])

        # set VQ (virtual queue) parameters
        for precedence, precedence_config in config['precedence'].items():
            precedence = int(precedence)
            qparams = self._calc_random_detect_queue_params(
                avg_pkt=precedence_config.get('average_packet'),
                max_thr=precedence_config.get('maximum_threshold'),
                limit=precedence_config.get('queue_limit'),
                min_thr=precedence_config.get('minimum_threshold'),
                mark_probability=precedence_config.get('mark_probability'),
                precedence=precedence
            )
            tmp = f'tc qdisc change dev {self._interface} handle {handle}:0 gred limit {qparams["limit"]} min {qparams["min_val"]} max {qparams["max_val"]} avpkt {qparams["avg_pkt"]} '
            tmp += f'burst {qparams["burst"]} bandwidth {bandwidth} probability {qparams["probability"]} DP {precedence} prio {8 - precedence:x}'
            self._cmd(tmp)

        # call base class
        super().update(config, direction)
