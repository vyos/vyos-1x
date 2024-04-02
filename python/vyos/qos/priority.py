# Copyright 2022-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

class Priority(QoSBase):
    _parent = 1

    # https://man7.org/linux/man-pages/man8/tc-prio.8.html
    def update(self, config, direction):
        if 'class' in config:
            class_id_max = self._get_class_max_id(config)
            bands = int(class_id_max) +1

            tmp = f'tc qdisc add dev {self._interface} root handle {self._parent:x}: prio bands {bands} priomap ' \
                  f'{class_id_max} {class_id_max} {class_id_max} {class_id_max} ' \
                  f'{class_id_max} {class_id_max} {class_id_max} {class_id_max} ' \
                  f'{class_id_max} {class_id_max} {class_id_max} {class_id_max} ' \
                  f'{class_id_max} {class_id_max} {class_id_max} {class_id_max} '
            self._cmd(tmp)

            for cls in config['class']:
                cls = int(cls)
                tmp = f'tc qdisc add dev {self._interface} parent {self._parent:x}:{cls:x} pfifo'
                self._cmd(tmp)

        # base class must be called last
        super().update(config, direction, priority=True)
