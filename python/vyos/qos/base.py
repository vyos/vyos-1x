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

import os

from vyos.base import Warning
from vyos.util import cmd
from vyos.util import dict_search
from vyos.util import read_file

class QoSBase:
    _debug = False
    _direction = ['egress']
    _parent = 0xffff

    def __init__(self, interface):
        if os.path.exists('/tmp/vyos.qos.debug'):
            self._debug = True
        self._interface = interface

    def _cmd(self, command):
        if self._debug:
            print(f'DEBUG/QoS: {command}')
        return cmd(command)

    def get_direction(self) -> list:
        return self._direction

    def _get_class_max_id(self, config) -> int:
        if 'class' in config:
            tmp = list(config['class'].keys())
            tmp.sort(key=lambda ii: int(ii))
            return tmp[-1]
        return None

    def _build_base_qdisc(self, config : dict, cls_id : int):
        """
        Add/replace qdisc for every class (also default is a class). This is
        a genetic method which need an implementation "per" queue-type.

        This matches the old mapping as defined in Perl here:
        https://github.com/vyos/vyatta-cfg-qos/blob/equuleus/lib/Vyatta/Qos/ShaperClass.pm#L223-L229
        """
        queue_type = dict_search('queue_type', config)
        default_tc = f'tc qdisc replace dev {self._interface} parent {self._parent}:{cls_id:x}'

        if queue_type == 'priority':
            handle = 0x4000 + cls_id
            default_tc += f' handle {handle:x}: prio'
            self._cmd(default_tc)

            queue_limit = dict_search('queue_limit', config)
            for ii in range(1, 4):
                tmp = f'tc qdisc replace dev {self._interface} parent {handle:x}:{ii:x} pfifo limit {queue_limit}'
                self._cmd(tmp)

        elif queue_type == 'fair-queue':
            default_tc += f' sfq'

            tmp = dict_search('queue_limit', config)
            if tmp: default_tc += f' limit {tmp}'

            self._cmd(default_tc)

        elif queue_type == 'fq-codel':
            default_tc += f' fq_codel'
            tmp = dict_search('codel_quantum', config)
            if tmp: default_tc += f' quantum {tmp}'

            tmp = dict_search('flows', config)
            if tmp: default_tc += f' flows {tmp}'

            tmp = dict_search('interval', config)
            if tmp: default_tc += f' interval {tmp}'

            tmp = dict_search('interval', config)
            if tmp: default_tc += f' interval {tmp}'

            tmp = dict_search('queue_limit', config)
            if tmp: default_tc += f' limit {tmp}'

            tmp = dict_search('target', config)
            if tmp: default_tc += f' target {tmp}'

            default_tc += f' noecn'

            self._cmd(default_tc)

        elif queue_type == 'random-detect':
            default_tc += f' red'

            self._cmd(default_tc)

        elif queue_type == 'drop-tail':
            default_tc += f' pfifo'

            tmp = dict_search('queue_limit', config)
            if tmp: default_tc += f' limit {tmp}'

            self._cmd(default_tc)

    def _rate_convert(self, rate) -> int:
        rates = {
            'bit'   : 1,
            'kbit'  : 1000,
            'mbit'  : 1000000,
            'gbit'  : 1000000000,
            'tbit'  : 1000000000000,
        }

        if rate == 'auto' or rate.endswith('%'):
            speed = read_file(f'/sys/class/net/{self._interface}/speed')
            if not speed.isnumeric():
                Warning('Interface speed cannot be determined (assuming 10 Mbit/s)')
                speed = 10
            if rate.endswith('%'):
                percent = rate.rstrip('%')
                speed = int(speed) * int(percent) // 100
            return int(speed) *1000000 # convert to MBit/s

        rate_numeric = int(''.join([n for n in rate if n.isdigit()]))
        rate_scale   = ''.join([n for n in rate if not n.isdigit()])

        if int(rate_numeric) <= 0:
            raise ValueError(f'{rate_numeric} is not a valid bandwidth <= 0')

        if rate_scale:
            return int(rate_numeric * rates[rate_scale])
        else:
            # No suffix implies Kbps just as Cisco IOS
            return int(rate_numeric * 1000)

    def update(self, config, direction, priority=None):
        """ method must be called from derived class after it has completed qdisc setup """
        if self._debug:
            import pprint
            pprint.pprint(config)

        if 'class' in config:
            for cls, cls_config in config['class'].items():
                self._build_base_qdisc(cls_config, int(cls))

                # every match criteria has it's tc instance
                filter_cmd = f'tc filter replace dev {self._interface} parent {self._parent:x}:'

                if priority:
                    filter_cmd += f' prio {cls}'
                elif 'priority' in cls_config:
                    prio = cls_config['priority']
                    filter_cmd += f' prio {prio}'

                filter_cmd += ' protocol all'

                if 'match' in cls_config:
                    for match, match_config in cls_config['match'].items():
                        if 'mark' in match_config:
                            mark = match_config['mark']
                            filter_cmd += f' handle {mark} fw'

                        for af in ['ip', 'ipv6']:
                            tc_af = af
                            if af == 'ipv6':
                                tc_af = 'ip6'

                            if af in match_config:
                                filter_cmd += ' u32'

                                tmp = dict_search(f'{af}.source.address', match_config)
                                if tmp: filter_cmd += f' match {tc_af} src {tmp}'

                                tmp = dict_search(f'{af}.source.port', match_config)
                                if tmp: filter_cmd += f' match {tc_af} sport {tmp} 0xffff'

                                tmp = dict_search(f'{af}.destination.address', match_config)
                                if tmp: filter_cmd += f' match {tc_af} dst {tmp}'

                                tmp = dict_search(f'{af}.destination.port', match_config)
                                if tmp: filter_cmd += f' match {tc_af} dport {tmp} 0xffff'

                                tmp = dict_search(f'{af}.protocol', match_config)
                                if tmp: filter_cmd += f' match {tc_af} protocol {tmp} 0xff'

                                # Will match against total length of an IPv4 packet and
                                # payload length of an IPv6 packet.
                                #
                                # IPv4 : match u16 0x0000 ~MAXLEN at 2
                                # IPv6 : match u16 0x0000 ~MAXLEN at 4
                                tmp = dict_search(f'{af}.max_length', match_config)
                                if tmp:
                                    # We need the 16 bit two's complement of the maximum
                                    # packet length
                                    tmp = hex(0xffff & ~int(tmp))

                                    if af == 'ip':
                                        filter_cmd += f' match u16 0x0000 {tmp} at 2'
                                    elif af == 'ipv6':
                                        filter_cmd += f' match u16 0x0000 {tmp} at 4'

                                # We match against specific TCP flags - we assume the IPv4
                                # header length is 20 bytes and assume the IPv6 packet is
                                # not using extension headers (hence a ip header length of 40 bytes)
                                # TCP Flags are set on byte 13 of the TCP header.
                                # IPv4 : match u8 X X at 33
                                # IPv6 : match u8 X X at 53
                                # with X = 0x02 for SYN and X = 0x10 for ACK
                                tmp = dict_search(f'{af}.tcp', match_config)
                                if tmp:
                                    mask = 0
                                    if 'ack' in tmp:
                                        mask |= 0x10
                                    if 'syn' in tmp:
                                        mask |= 0x02
                                    mask = hex(mask)

                                    if af == 'ip':
                                        filter_cmd += f' match u8 {mask} {mask} at 33'
                                    elif af == 'ipv6':
                                        filter_cmd += f' match u8 {mask} {mask} at 53'

                else:

                    filter_cmd += ' basic'

                # The police block allows limiting of the byte or packet rate of
                # traffic matched by the filter it is attached to.
                # https://man7.org/linux/man-pages/man8/tc-police.8.html
                if any(tmp in ['exceed', 'bandwidth', 'burst'] for tmp in cls_config):
                    filter_cmd += f' action police'

                if 'exceed' in cls_config:
                    action = cls_config['exceed']
                    filter_cmd += f' conform-exceed {action}'
                    if 'not_exceed' in cls_config:
                        action = cls_config['not_exceed']
                        filter_cmd += f'/{action}'

                if 'bandwidth' in cls_config:
                    rate = self._rate_convert(cls_config['bandwidth'])
                    filter_cmd += f' rate {rate}'

                if 'burst' in cls_config:
                    burst = cls_config['burst']
                    filter_cmd += f' burst {burst}'

                cls = int(cls)
                filter_cmd += f' flowid {self._parent:x}:{cls:x}'
                self._cmd(filter_cmd)

        if 'default' in config:
            if 'class' in config:
                class_id_max = self._get_class_max_id(config)
                default_cls_id = int(class_id_max) +1
                self._build_base_qdisc(config['default'], default_cls_id)

            filter_cmd = f'tc filter replace dev {self._interface} parent {self._parent:x}: '
            filter_cmd += 'prio 255 protocol all basic'

            # The police block allows limiting of the byte or packet rate of
            # traffic matched by the filter it is attached to.
            # https://man7.org/linux/man-pages/man8/tc-police.8.html
            if any(tmp in ['exceed', 'bandwidth', 'burst'] for tmp in config['default']):
                filter_cmd += f' action police'

            if 'exceed' in config['default']:
                action = config['default']['exceed']
                filter_cmd += f' conform-exceed {action}'
                if 'not_exceed' in config['default']:
                    action = config['default']['not_exceed']
                    filter_cmd += f'/{action}'

            if 'bandwidth' in config['default']:
                rate = self._rate_convert(config['default']['bandwidth'])
                filter_cmd += f' rate {rate}'

            if 'burst' in config['default']:
                burst = config['default']['burst']
                filter_cmd += f' burst {burst}'

            if 'class' in config:
                filter_cmd += f' flowid {self._parent:x}:{default_cls_id:x}'

            self._cmd(filter_cmd)

