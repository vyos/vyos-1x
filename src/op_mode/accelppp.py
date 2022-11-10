#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import sys

import vyos.accel_ppp
import vyos.opmode

from vyos.configquery import ConfigTreeQuery
from vyos.util import rc_cmd


accel_dict = {
    'ipoe': {
        'port': 2002,
        'path': 'service ipoe-server'
    },
    'pppoe': {
        'port': 2001,
        'path': 'service pppoe-server'
    },
    'pptp': {
        'port': 2003,
        'path': 'vpn pptp'
    },
    'l2tp': {
        'port': 2004,
        'path': 'vpn l2tp'
    },
    'sstp': {
        'port': 2005,
        'path': 'vpn sstp'
    }
}


def _get_raw_statistics(accel_output, pattern):
    return vyos.accel_ppp.get_server_statistics(accel_output, pattern, sep=':')


def _get_raw_sessions(port):
    cmd_options = 'show sessions ifname,username,ip,ip6,ip6-dp,type,state,' \
                  'uptime-raw,calling-sid,called-sid,sid,comp,rx-bytes-raw,' \
                  'tx-bytes-raw,rx-pkts,tx-pkts'
    output = vyos.accel_ppp.accel_cmd(port, cmd_options)
    parsed_data: list[dict[str, str]] = vyos.accel_ppp.accel_out_parse(
        output.splitlines())
    return parsed_data


def _verify(func):
    """Decorator checks if accel-ppp protocol
    ipoe/pppoe/pptp/l2tp/sstp is configured

    for example:
        service ipoe-server
        vpn sstp
    """
    from functools import wraps

    @wraps(func)
    def _wrapper(*args, **kwargs):
        config = ConfigTreeQuery()
        protocol_list = accel_dict.keys()
        protocol = kwargs.get('protocol')
        # unknown or incorrect protocol query
        if protocol not in protocol_list:
            unconf_message = f'unknown protocol "{protocol}"'
            raise vyos.opmode.UnconfiguredSubsystem(unconf_message)
        # Check if config does not exist
        config_protocol_path = accel_dict[protocol]['path']
        if not config.exists(config_protocol_path):
            unconf_message = f'"{config_protocol_path}" is not configured'
            raise vyos.opmode.UnconfiguredSubsystem(unconf_message)
        return func(*args, **kwargs)

    return _wrapper


@_verify
def show_statistics(raw: bool, protocol: str):
    """show accel-cmd statistics
    CPU utilization and amount of sessions

    protocol: ipoe/pppoe/ppptp/l2tp/sstp
    """
    pattern = f'{protocol}:'
    port = accel_dict[protocol]['port']
    rc, output = rc_cmd(f'/usr/bin/accel-cmd -p {port} show stat')

    if raw:
        return _get_raw_statistics(output, pattern)

    return output


@_verify
def show_sessions(raw: bool, protocol: str):
    """show accel-cmd sessions

    protocol: ipoe/pppoe/ppptp/l2tp/sstp
    """
    port = accel_dict[protocol]['port']
    if raw:
        return _get_raw_sessions(port)

    return vyos.accel_ppp.accel_cmd(port,
                                    'show sessions ifname,username,ip,ip6,ip6-dp,'
                                    'calling-sid,rate-limit,state,uptime,rx-bytes,tx-bytes')


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
