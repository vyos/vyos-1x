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


class CAKE(QoSBase):
    """
    https://man7.org/linux/man-pages/man8/tc-cake.8.html
    """

    _direction = ['egress']

    flow_isolation_map = {
        'blind': 'flowblind',
        'src-host': 'srchost',
        'dst-host': 'dsthost',
        'dual-dst-host': 'dual-dsthost',
        'dual-src-host': 'dual-srchost',
        'triple-isolate': 'triple-isolate',
        'flow': 'flows',
        'host': 'hosts',
    }

    def update(self, config, direction):
        tmp = f'tc qdisc add dev {self._interface} root handle 1: cake {direction}'
        if 'bandwidth' in config:
            bandwidth = self._rate_convert(config['bandwidth'])
            tmp += f' bandwidth {bandwidth}'

        if 'rtt' in config:
            rtt = config['rtt']
            tmp += f' rtt {rtt}ms'

        if 'flow_isolation' in config:
            isolation_value = self.flow_isolation_map.get(config['flow_isolation'])

            if isolation_value is not None:
                tmp += f' {isolation_value}'
            else:
                raise ValueError(
                    f'Invalid flow isolation parameter: {config["flow_isolation"]}'
                )

        tmp += ' nat' if 'flow_isolation_nat' in config else ' nonat'

        self._cmd(tmp)

        # call base class
        super().update(config, direction)
