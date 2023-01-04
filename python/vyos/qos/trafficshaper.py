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

from math import ceil
from vyos.qos.base import QoSBase

# Kernel limits on quantum (bytes)
MAXQUANTUM = 200000
MINQUANTUM = 1000

class TrafficShaper(QoSBase):
    _parent = 1

    # https://man7.org/linux/man-pages/man8/tc-htb.8.html
    def update(self, config, direction):
        class_id_max = 0
        if 'class' in config:
            tmp = list(config['class'])
            tmp.sort()
            class_id_max = tmp[-1]

        r2q = 10
        # bandwidth is a mandatory CLI node
        speed = self._rate_convert(config['bandwidth'])
        speed_bps = int(speed) // 8

        # need a bigger r2q if going fast than 16 mbits/sec
        if (speed_bps // r2q) >= MAXQUANTUM: # integer division
            r2q = ceil(speed_bps // MAXQUANTUM)
        else:
            # if there is a slow class then may need smaller value
            if 'class' in config:
                min_speed = speed_bps
                for cls, cls_options in config['class'].items():
                    # find class with the lowest bandwidth used
                    if 'bandwidth' in cls_options:
                        bw_bps = int(self._rate_convert(cls_options['bandwidth'])) // 8 # bandwidth in bytes per second
                        if bw_bps < min_speed:
                            min_speed = bw_bps

                while (r2q > 1) and (min_speed // r2q) < MINQUANTUM:
                    tmp = r2q -1
                    if (speed_bps // tmp) >= MAXQUANTUM:
                        break
                    r2q = tmp


        default_minor_id = int(class_id_max) +1
        tmp = f'tc qdisc replace dev {self._interface} root handle {self._parent:x}: htb r2q {r2q} default {default_minor_id:x}' # default is in hex
        self._cmd(tmp)

        tmp = f'tc class replace dev {self._interface} parent {self._parent:x}: classid {self._parent:x}:1 htb rate {speed}'
        self._cmd(tmp)

        if 'class' in config:
            for cls, cls_config in config['class'].items():
                # class id is used later on and passed as hex, thus this needs to be an int
                cls = int(cls)

                # bandwidth is a mandatory CLI node
                rate = self._rate_convert(cls_config['bandwidth'])
                burst = cls_config['burst']
                quantum = cls_config['codel_quantum']

                tmp = f'tc class replace dev {self._interface} parent {self._parent:x}:1 classid {self._parent:x}:{cls:x} htb rate {rate} burst {burst} quantum {quantum}'
                if 'priority' in cls_config:
                    priority = cls_config['priority']
                    tmp += f' prio {priority}'
                self._cmd(tmp)

                tmp = f'tc qdisc replace dev {self._interface} parent {self._parent:x}:{cls:x} sfq'
                self._cmd(tmp)

        if 'default' in config:
                rate = self._rate_convert(config['default']['bandwidth'])
                burst = config['default']['burst']
                quantum = config['default']['codel_quantum']
                tmp = f'tc class replace dev {self._interface} parent {self._parent:x}:1 classid {self._parent:x}:{default_minor_id:x} htb rate {rate} burst {burst} quantum {quantum}'
                if 'priority' in config['default']:
                    priority = config['default']['priority']
                    tmp += f' prio {priority}'
                self._cmd(tmp)

                tmp = f'tc qdisc replace dev {self._interface} parent {self._parent:x}:{default_minor_id:x} sfq'
                self._cmd(tmp)

        # call base class
        super().update(config, direction)

class TrafficShaperHFSC(TrafficShaper):
    def update(self, config, direction):
        # call base class
        super().update(config, direction)

