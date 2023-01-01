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

class FQCodel(QoSBase):
    # https://man7.org/linux/man-pages/man8/tc-fq_codel.8.html
    def update(self, config, direction):
        tmp = f'tc qdisc add dev {self._interface} root fq_codel'

        if 'codel_quantum' in config:
            tmp += f' quantum {config["codel_quantum"]}'
        if 'flows' in config:
            tmp += f' flows {config["flows"]}'
        if 'interval' in config:
            interval = int(config['interval']) * 1000
            tmp += f' interval {interval}'
        if 'queue_limit' in config:
            tmp += f' limit {config["queue_limit"]}'
        if 'target' in config:
            target = int(config['target']) * 1000
            tmp += f' target {target}'

        tmp += f' noecn'
        self._cmd(tmp)

        # call base class
        super().update(config, direction)
