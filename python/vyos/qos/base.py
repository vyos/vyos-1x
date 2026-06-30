# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
from vyos.ifconfig import Interface
from vyos.utils.process import cmdl
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

    def _cmdl(self, command):
        if not isinstance(command, list):
            raise TypeError(f'_cmdl() requires a list, got {type(command).__name__}')
        if self._debug:
            print(f'DEBUG/QoS: {command}')
        return cmdl(command)

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
            # left shift operation aligns the DSCP/TOS value with its bit position in the IP header.
            return int(value) << 2

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
        default_tc = ['tc', 'qdisc', 'replace', 'dev', self._interface,
                      'parent', f'{self._parent}:{cls_id:x}']

        if queue_type == 'priority':
            handle = 0x4000 + cls_id
            default_tc += ['handle', f'{handle:x}:', 'prio']
            self._cmdl(default_tc)

            queue_limit = dict_search('queue_limit', config)
            for ii in range(1, 4):
                tmp = ['tc', 'qdisc', 'replace', 'dev', self._interface,
                       'parent', f'{handle:x}:{ii:x}', 'pfifo']
                if queue_limit: tmp += ['limit', str(queue_limit)]
                self._cmdl(tmp)

        elif queue_type == 'fair-queue':
            default_tc += ['sfq']

            tmp = dict_search('queue_limit', config)
            if tmp: default_tc += ['limit', str(tmp)]

            self._cmdl(default_tc)

        elif queue_type == 'fq-codel':
            default_tc += ['fq_codel']
            tmp = dict_search('codel_quantum', config)
            if tmp: default_tc += ['quantum', str(tmp)]

            tmp = dict_search('flows', config)
            if tmp: default_tc += ['flows', str(tmp)]

            tmp = dict_search('interval', config)
            if tmp: default_tc += ['interval', f'{tmp}ms']

            tmp = dict_search('queue_limit', config)
            if tmp: default_tc += ['limit', str(tmp)]

            tmp = dict_search('target', config)
            if tmp: default_tc += ['target', f'{tmp}ms']

            default_tc += ['noecn']

            self._cmdl(default_tc)

        elif queue_type == 'random-detect':
            default_tc += ['red']

            qparams = self._calc_random_detect_queue_params(
                avg_pkt=dict_search('average_packet', config) or 1024,
                max_thr=dict_search('maximum_threshold', config) or 18,
                limit=dict_search('queue_limit', config),
                min_thr=dict_search('minimum_threshold', config),
                mark_probability=dict_search('mark_probability', config) or 10
            )

            default_tc += ['limit', str(qparams['limit']), 'avpkt', str(qparams['avg_pkt'])]
            default_tc += ['max', str(qparams['max_val']), 'min', str(qparams['min_val'])]
            default_tc += ['burst', str(qparams['burst']), 'probability', str(qparams['probability'])]

            self._cmdl(default_tc)

        elif queue_type == 'drop-tail':
            default_tc += ['pfifo']

            tmp = dict_search('queue_limit', config)
            if tmp: default_tc += ['limit', str(tmp)]

            self._cmdl(default_tc)

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
            # interfaces have the appropriate speed file, but you cannot read it:
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


                # Get DSCP value for packet remarking via tc pedit action
                set_dscp = dict_search('set_dscp', cls_config)
                dscp_value = None
                if set_dscp:
                    dscp_value = str(self._get_dsfield(set_dscp))

                # every match criteria has it's tc instance
                filter_cmd_base = ['tc', 'filter', 'add', 'dev', self._interface,
                                    'parent', f'{self._parent:x}:']

                if priority:
                    filter_cmd_base += ['prio', str(cls)]
                elif 'priority' in cls_config:
                    prio = cls_config['priority']
                    filter_cmd_base += ['prio', str(prio)]

                if 'match' in cls_config:
                    has_filter = False
                    has_action_policy = any(tmp in ['exceed', 'bandwidth', 'burst'] for tmp in cls_config)
                    max_index = len(cls_config['match'])
                    for index, (match, match_config) in enumerate(cls_config['match'].items(), start=1):
                        filter_cmd = list(filter_cmd_base)
                        if not has_filter:
                            for key in ['mark', 'vif', 'ip', 'ipv6', 'interface', 'ether']:
                                if key in match_config:
                                    has_filter = True
                                    break

                        filter_protocol = (
                            dict_search(f'ether.protocol', match_config) or 'all'
                        )
                        filter_cmd += ['protocol', filter_protocol]

                        if self.qostype in ['shaper', 'shaper_hfsc'] and 'prio' not in filter_cmd:
                            filter_cmd += ['prio', str(index)]

                        if 'mark' in match_config:
                            mark = match_config['mark']
                            filter_cmd += ['handle', str(mark), 'fw']

                        if 'vif' in match_config:
                            vif = match_config['vif']
                            filter_cmd += ['basic', 'match', f'meta(vlan mask 0xfff eq {vif})']
                        elif 'interface' in match_config:
                            iif_name = match_config['interface']
                            iif = Interface(iif_name).get_ifindex()
                            filter_cmd += ['basic', 'match', f'meta(rt_iif eq {iif})']

                        for af in ['ip', 'ipv6', 'ether']:
                            tc_af = af
                            if af == 'ipv6':
                                tc_af = 'ip6'

                            if af in match_config:
                                filter_cmd += ['u32']

                                if af == 'ether':
                                    src = dict_search(f'{af}.source', match_config)
                                    if src: filter_cmd += ['match', tc_af, 'src', str(src)]

                                    dst = dict_search(f'{af}.destination', match_config)
                                    if dst: filter_cmd += ['match', tc_af, 'dst', str(dst)]

                                    if not src and not dst:
                                        filter_cmd += ['match', 'u32', '0', '0']
                                else:
                                    tmp = dict_search(f'{af}.source.address', match_config)
                                    if tmp: filter_cmd += ['match', tc_af, 'src', str(tmp)]

                                    tmp = dict_search(f'{af}.source.port', match_config)
                                    if tmp: filter_cmd += ['match', tc_af, 'sport', str(tmp), '0xffff']

                                    tmp = dict_search(f'{af}.destination.address', match_config)
                                    if tmp: filter_cmd += ['match', tc_af, 'dst', str(tmp)]

                                    tmp = dict_search(f'{af}.destination.port', match_config)
                                    if tmp: filter_cmd += ['match', tc_af, 'dport', str(tmp), '0xffff']
                                    ###
                                    tmp = dict_search(f'{af}.protocol', match_config)
                                    if tmp:
                                        tmp = get_protocol_by_name(tmp)
                                        filter_cmd += ['match', tc_af, 'protocol', str(tmp), '0xff']

                                    tmp = dict_search(f'{af}.dscp', match_config)
                                    if tmp:
                                        tmp = self._get_dsfield(tmp)
                                        if af == 'ip':
                                            filter_cmd += ['match', tc_af, 'dsfield', str(tmp), '0xff']
                                        elif af == 'ipv6':
                                            filter_cmd += ['match', 'u16', str(tmp), '0x0ff0', 'at', '0']

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
                                            filter_cmd += ['match', 'u16', '0x0000', str(tmp), 'at', '2']
                                        elif af == 'ipv6':
                                            filter_cmd += ['match', 'u16', '0x0000', str(tmp), 'at', '4']

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
                                            filter_cmd += ['match', 'u8', str(mask), str(mask), 'at', '33']
                                        elif af == 'ipv6':
                                            filter_cmd += ['match', 'u8', str(mask), str(mask), 'at', '53']

                        # Build pedit action to rewrite DSCP on matched packets.
                        # retain 0xfc preserves ECN bits (bottom 2 bits of TOS/Traffic Class).
                        # Non-IP match types skip pedit to avoid corrupting
                        # non-IP packets, unless ether protocol is ip or ipv6.
                        dscp_action = []
                        if dscp_value is not None:
                            proto = str(filter_protocol).lower()
                            is_ipv4 = 'ip' in match_config or proto in ('ip', '0x0800', '2048')
                            is_ipv6 = 'ipv6' in match_config or proto in ('ipv6', '0x86dd', '34525')
                            if is_ipv4:
                                dscp_action = ['action', 'pedit', 'ex', 'munge', 'ip',
                                               'dsfield', 'set', dscp_value, 'retain', '0xfc',
                                               'pipe', 'action', 'csum', 'ip4h']
                            elif is_ipv6:
                                dscp_action = ['action', 'pedit', 'ex', 'munge',
                                               'ip6', 'traffic_class', 'set', dscp_value, 'retain', '0xfc']

                        if index != max_index or not has_action_policy:
                            # avoid duplicate last match rule
                            cls = int(cls)
                            # add pedit before flowid for filters without police
                            if dscp_action:
                                filter_cmd += dscp_action
                            filter_cmd += ['flowid', f'{self._parent:x}:{cls:x}']
                            self._cmdl(filter_cmd)

                    vlan_expression = "match.*.vif"
                    match_vlan = jmespath.search(vlan_expression, cls_config)

                    if has_action_policy and has_filter:
                        # For "vif" "basic match" is used instead of "action police" T5961
                        if not match_vlan:
                            # chain pedit before police with pipe
                            if dscp_action:
                                filter_cmd += dscp_action + ['pipe']
                            filter_cmd += ['action', 'police']

                            if 'exceed' in cls_config:
                                action = cls_config['exceed']
                                filter_cmd += ['conform-exceed', str(action)]
                            if 'not_exceed' in cls_config:
                                action = cls_config['not_exceed']
                                filter_cmd[-1] += f'/{action}'

                            if 'bandwidth' in cls_config:
                                rate = self._rate_convert(cls_config['bandwidth'])
                                filter_cmd += ['rate', str(rate)]

                            if 'burst' in cls_config:
                                burst = cls_config['burst']
                                filter_cmd += ['burst', str(burst)]

                            if 'mtu' in cls_config:
                                mtu = cls_config['mtu']
                                filter_cmd += ['mtu', str(mtu)]
                        elif dscp_action:
                            # vlan match skips police (T5961) but still needs pedit
                            filter_cmd += dscp_action

                        cls = int(cls)
                        filter_cmd += ['flowid', f'{self._parent:x}:{cls:x}']
                        self._cmdl(filter_cmd)

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

            # Default class has no match filters, so catch-all filters
            # are needed to attach the pedit action for DSCP remarking.
            # Separate filters per protocol to avoid corrupting non-IP packets (e.g. ARP).
            # IPv4 uses u32 catch-all, IPv6 uses basic classifier (u32 doesn't support protocol ipv6).
            # prio 255/256 ensures class filters match first.
            set_dscp = dict_search('set_dscp', config['default'])
            if set_dscp and self.qostype == 'shaper':
                dscp_value = str(self._get_dsfield(set_dscp))
                filter_cmd = ['tc', 'filter', 'replace', 'dev', self._interface,
                              'parent', f'{self._parent:x}:']
                filter_cmd += ['prio', '255', 'protocol', 'ip', 'u32',
                               'match', 'u32', '0', '0']
                filter_cmd += ['action', 'pedit', 'ex', 'munge',
                               'ip', 'dsfield', 'set', dscp_value, 'retain', '0xfc',
                               'pipe', 'action', 'csum', 'ip4h']
                filter_cmd += ['flowid', f'{self._parent:x}:{default_cls_id:x}']
                self._cmdl(filter_cmd)

                filter_cmd = ['tc', 'filter', 'replace', 'dev', self._interface,
                              'parent', f'{self._parent:x}:']
                filter_cmd += ['prio', '256', 'protocol', 'ipv6', 'basic']
                filter_cmd += ['action', 'pedit', 'ex', 'munge', 'ip6',
                               'traffic_class', 'set', dscp_value, 'retain', '0xfc']
                filter_cmd += ['flowid', f'{self._parent:x}:{default_cls_id:x}']
                self._cmdl(filter_cmd)

        if self.qostype == 'limiter':
            if 'default' in config:
                filter_cmd = ['tc', 'filter', 'replace', 'dev', self._interface,
                              'parent', f'{self._parent:x}:',
                              'prio', '255', 'protocol', 'all', 'basic']

                # The police block allows limiting of the byte or packet rate of
                # traffic matched by the filter it is attached to.
                # https://man7.org/linux/man-pages/man8/tc-police.8.html
                if any(tmp in ['exceed', 'bandwidth', 'burst'] for tmp in
                       config['default']):
                    filter_cmd += ['action', 'police']

                if 'exceed' in config['default']:
                    action = config['default']['exceed']
                    filter_cmd += ['conform-exceed', str(action)]
                    if 'not_exceed' in config['default']:
                        action = config['default']['not_exceed']
                        filter_cmd[-1] += f'/{action}'

                if 'bandwidth' in config['default']:
                    rate = self._rate_convert(config['default']['bandwidth'])
                    filter_cmd += ['rate', str(rate)]

                if 'burst' in config['default']:
                    burst = config['default']['burst']
                    filter_cmd += ['burst', str(burst)]

                if 'mtu' in config['default']:
                    mtu = config['default']['mtu']
                    filter_cmd += ['mtu', str(mtu)]

                if 'class' in config:
                    filter_cmd += ['flowid', f'{self._parent:x}:{default_cls_id:x}']

                self._cmdl(filter_cmd)
