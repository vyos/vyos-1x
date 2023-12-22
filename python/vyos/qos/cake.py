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
    _direction = ['egress']

    # https://man7.org/linux/man-pages/man8/tc-cake.8.html
    def update(self, config, direction):
        tmp = f'tc qdisc add dev {self._interface} root handle 1: cake {direction}'
        if 'bandwidth' in config:
            bandwidth = self._rate_convert(config['bandwidth'])
            tmp += f' bandwidth {bandwidth}'

        if 'rtt' in config:
            rtt = config['rtt']
            tmp += f' rtt {rtt}ms'

        if 'flow_isolation' in config:
            if 'blind' in config['flow_isolation']:
                tmp += f' flowblind'
            if 'dst_host' in config['flow_isolation']:
                tmp += f' dsthost'
            if 'dual_dst_host' in config['flow_isolation']:
                tmp += f' dual-dsthost'
            if 'dual_src_host' in config['flow_isolation']:
                tmp += f' dual-srchost'
            if 'triple_isolate' in config['flow_isolation']:
                tmp += f' triple-isolate'
            if 'flow' in config['flow_isolation']:
                tmp += f' flows'
            if 'host' in config['flow_isolation']:
                tmp += f' hosts'
            if 'nat' in config['flow_isolation']:
                tmp += f' nat'
            if 'src_host' in config['flow_isolation']:
                tmp += f' srchost '
        else:
            tmp += f' nonat'

        self._cmd(tmp)

        # call base class
        super().update(config, direction)
