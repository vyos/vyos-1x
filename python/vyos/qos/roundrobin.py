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


class RoundRobin(QoSBase):
    _parent = 1

    # https://man7.org/linux/man-pages/man8/tc-drr.8.html
    def update(self, config, direction):
        tmp = f'tc qdisc add dev {self._interface} root handle 1: drr'
        self._cmd(tmp)

        if 'class' in config:
            for cls in config['class']:
                cls = int(cls)
                tmp = f'tc class replace dev {self._interface} parent 1:1 classid 1:{cls:x} drr'
                self._cmd(tmp)

                tmp = f'tc qdisc replace dev {self._interface} parent 1:{cls:x} pfifo'
                self._cmd(tmp)

        if 'default' in config:
            class_id_max = self._get_class_max_id(config)
            default_cls_id = int(class_id_max) + 1 if class_id_max else 1

            # class ID via CLI is in range 1-4095, thus 1000 hex = 4096
            tmp = f'tc class replace dev {self._interface} parent 1:1 classid 1:{default_cls_id:x} drr'
            self._cmd(tmp)

            # You need to add at least one filter to classify packets
            # otherwise, all packets will be dropped.
            filter_cmd = (
                f'tc filter replace dev {self._interface} '
                f'parent {self._parent:x}: prio {default_cls_id} protocol all '
                'u32 match u32 0 0 '
                f'flowid {self._parent}:{default_cls_id}'
            )
            self._cmd(filter_cmd)

        # call base class
        super().update(config, direction, priority=True)
