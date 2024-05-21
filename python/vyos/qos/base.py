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

import os
import jmespath

from vyos.base import Warning
from vyos.utils.process import cmd
from vyos.utils.dict import dict_search
from vyos.utils.file import read_file

from vyos.utils.network import get_protocol_by_name


class QoSBase:
    _debug = False
    _direction = ['egress']
    _parent = 0xffff
    _dsfields = {
        "default": 0x0,
        "lowdelay": 0x10,
        "throughput": 0x08,
        "reliability": 0x04,
        "mincost": 0x02,
        "priority": 0x20,
        "immediate": 0x40,
        "flash": 0x60,
        "flash-override": 0x80,
        "critical": 0x0A,
        "internet": 0xC0,
        "network": 0xE0,
        "AF11": 0x28,
        "AF12": 0x30,
        "AF13": 0x38,
        "AF21": 0x48,
        "AF22": 0x50,
        "AF23": 0x58,
        "AF31": 0x68,
        "AF32": 0x70,
        "AF33": 0x78,
        "AF41": 0x88,
        "AF42": 0x90,
        "AF43": 0x98,
        "CS1": 0x20,
        "CS2": 0x40,
        "CS3": 0x60,
        "CS4": 0x80,
        "CS5": 0xA0,
        "CS6": 0xC0,
        "CS7": 0xE0,
        "EF": 0xB8
    }
    qostype = None

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

    def _get_dsfield(self, value):
        if value in self._dsfields:
            return self._dsfields[value]
        else:
            return value

    def _calc_random_detect_queue_params(self, avg_pkt, max_thr, limit=None, min_thr=None,
                                         mark_probability=None, precedence=0):
        params = dict()
        avg_pkt = int(avg_pkt)
        max_thr = int(max_thr)
        mark_probability = int(mark_probability)
        limit = int(limit) if limit else 4 * max_thr
        min_thr = int(min_thr) if min_thr else ((9 + precedence) * max_thr) // 18

        params['avg_pkt'] = avg_pkt
        params['limit'] = limit * avg_pkt
        params['min_val'] = min_thr * avg_pkt
        params['max_val'] = max_thr * avg_pkt
        params['burst'] = (2 * min_thr + max_thr) // 3
        params['probability'] = 1 / mark_probability

        return params

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
                tmp = f'tc qdisc replace dev {self._interface} parent {handle:x}:{ii:x} pfifo'
                if queue_limit: tmp += f' limit {queue_limit}'
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
            if tmp: default_tc += f' interval {tmp}ms'

            tmp = dict_search('queue_limit', config)
            if tmp: default_tc += f' limit {tmp}'

            tmp = dict_search('target', config)
            if tmp: default_tc += f' target {tmp}ms'

            default_tc += f' noecn'

            self._cmd(default_tc)

        elif queue_type == 'random-detect':
            default_tc += f' red'

            qparams = self._calc_random_detect_queue_params(
                avg_pkt=dict_search('average_packet', config),
                max_thr=dict_search('maximum_threshold', config),
                limit=dict_search('queue_limit', config),
                min_thr=dict_search('minimum_threshold', config),
                mark_probability=dict_search('mark_probability', config)
            )

            default_tc += f' limit {qparams["limit"]} avpkt {qparams["avg_pkt"]}'
            default_tc += f' max {qparams["max_val"]} min {qparams["min_val"]}'
            default_tc += f' burst {qparams["burst"]} probability {qparams["probability"]}'

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
            speed = 1000
            default_speed = speed
            # Not all interfaces have valid entries in the speed file. PPPoE
            # interfaces have the appropriate speed file, but you can not read it:
            # cat: /sys/class/net/pppoe7/speed: Invalid argument
            try:
                speed = read_file(f'/sys/class/net/{self._interface}/speed')
                if not speed.isnumeric():
                    Warning('Interface speed cannot be determined (assuming 1000 Mbit/s)')
                if int(speed) < 1:
                    speed = default_speed
                if rate.endswith('%'):
                    percent = rate.rstrip('%')
                    speed = int(speed) * int(percent) // 100
            except:
                pass

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
                filter_cmd_base = f'tc filter add dev {self._interface} parent {self._parent:x}:'

                if priority:
                    filter_cmd_base += f' prio {cls}'
                elif 'priority' in cls_config:
                    prio = cls_config['priority']
                    filter_cmd_base += f' prio {prio}'

                filter_cmd_base += ' protocol all'

                if 'match' in cls_config:
                    has_filter = False
                    for index, (match, match_config) in enumerate(cls_config['match'].items(), start=1):
                        filter_cmd = filter_cmd_base
                        if not has_filter:
                            for key in ['mark', 'vif', 'ip', 'ipv6']:
                                if key in match_config:
                                    has_filter = True
                                    break

                        if self.qostype == 'shaper' and 'prio ' not in filter_cmd:
                            filter_cmd += f' prio {index}'
                        if 'mark' in match_config:
                            mark = match_config['mark']
                            filter_cmd += f' handle {mark} fw'
                        if 'vif' in match_config:
                            vif = match_config['vif']
                            filter_cmd += f' basic match "meta(vlan mask 0xfff eq {vif})"'

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
                                if tmp:
                                    tmp = get_protocol_by_name(tmp)
                                    filter_cmd += f' match {tc_af} protocol {tmp} 0xff'

                                tmp = dict_search(f'{af}.dscp', match_config)
                                if tmp:
                                    tmp = self._get_dsfield(tmp)
                                    if af == 'ip':
                                        filter_cmd += f' match {tc_af} dsfield {tmp} 0xff'
                                    elif af == 'ipv6':
                                        filter_cmd += f' match u16 {tmp} 0x0ff0 at 0'

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

                                cls = int(cls)
                                filter_cmd += f' flowid {self._parent:x}:{cls:x}'
                                self._cmd(filter_cmd)

                    vlan_expression = "match.*.vif"
                    match_vlan = jmespath.search(vlan_expression, cls_config)

                    if any(tmp in ['exceed', 'bandwidth', 'burst'] for tmp in cls_config) \
                        and has_filter:
                        # For "vif" "basic match" is used instead of "action police" T5961
                        if not match_vlan:
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

                            if 'mtu' in cls_config:
                                mtu = cls_config['mtu']
                                filter_cmd += f' mtu {mtu}'

                        cls = int(cls)
                        filter_cmd += f' flowid {self._parent:x}:{cls:x}'
                        self._cmd(filter_cmd)

                # The police block allows limiting of the byte or packet rate of
                # traffic matched by the filter it is attached to.
                # https://man7.org/linux/man-pages/man8/tc-police.8.html

                # T5295: We do not handle rate via tc filter directly,
                # but rather set the tc filter to direct traffic to the correct tc class flow.
                #
                # if any(tmp in ['exceed', 'bandwidth', 'burst'] for tmp in cls_config):
                #     filter_cmd += f' action police'
                #
                # if 'exceed' in cls_config:
                #     action = cls_config['exceed']
                #     filter_cmd += f' conform-exceed {action}'
                #     if 'not_exceed' in cls_config:
                #         action = cls_config['not_exceed']
                #         filter_cmd += f'/{action}'
                #
                # if 'bandwidth' in cls_config:
                #     rate = self._rate_convert(cls_config['bandwidth'])
                #     filter_cmd += f' rate {rate}'
                #
                # if 'burst' in cls_config:
                #     burst = cls_config['burst']
                #     filter_cmd += f' burst {burst}'

        if 'default' in config:
            default_cls_id = 1
            if 'class' in config:
                class_id_max = self._get_class_max_id(config)
                default_cls_id = int(class_id_max) +1
            self._build_base_qdisc(config['default'], default_cls_id)

        if self.qostype == 'limiter':
            if 'default' in config:
                filter_cmd = f'tc filter replace dev {self._interface} parent {self._parent:x}: '
                filter_cmd += 'prio 255 protocol all basic'

                # The police block allows limiting of the byte or packet rate of
                # traffic matched by the filter it is attached to.
                # https://man7.org/linux/man-pages/man8/tc-police.8.html
                if any(tmp in ['exceed', 'bandwidth', 'burst'] for tmp in
                       config['default']):
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

                if 'mtu' in config['default']:
                    mtu = config['default']['mtu']
                    filter_cmd += f' mtu {mtu}'

                if 'class' in config:
                    filter_cmd += f' flowid {self._parent:x}:{default_cls_id:x}'

                self._cmd(filter_cmd)
