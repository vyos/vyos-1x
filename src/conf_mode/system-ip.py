#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os

from sys import exit
from copy import deepcopy
from vyos.config import Config
from vyos import ConfigError
from vyos.util import call

from vyos import airbag
airbag.enable()

default_config_data = {
    'arp_table': 8192,
    'ipv4_forward': '1',
    'mp_unreach_nexthop': '0',
    'mp_layer4_hashing': '0'
}

def sysctl(name, value):
    call('sysctl -wq {}={}'.format(name, value))

def get_config():
    ip_opt = deepcopy(default_config_data)
    conf = Config()
    conf.set_level('system ip')
    if conf.exists(''):
        if conf.exists('arp table-size'):
            ip_opt['arp_table'] = int(conf.return_value('arp table-size'))

        if conf.exists('disable-forwarding'):
            ip_opt['ipv4_forward'] = '0'

        if conf.exists('multipath ignore-unreachable-nexthops'):
            ip_opt['mp_unreach_nexthop'] = '1'

        if conf.exists('multipath layer4-hashing'):
            ip_opt['mp_layer4_hashing'] = '1'

    return ip_opt

def verify(ip_opt):
    pass

def generate(ip_opt):
    pass

def apply(ip_opt):
    # apply ARP threshold values
    sysctl('net.ipv4.neigh.default.gc_thresh3', ip_opt['arp_table'])
    sysctl('net.ipv4.neigh.default.gc_thresh2', ip_opt['arp_table'] // 2)
    sysctl('net.ipv4.neigh.default.gc_thresh1', ip_opt['arp_table'] // 8)

    # enable/disable IPv4 forwarding
    with open('/proc/sys/net/ipv4/conf/all/forwarding', 'w') as f:
        f.write(ip_opt['ipv4_forward'])

    # configure multipath
    sysctl('net.ipv4.fib_multipath_use_neigh', ip_opt['mp_unreach_nexthop'])
    sysctl('net.ipv4.fib_multipath_hash_policy', ip_opt['mp_layer4_hashing'])

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
