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
import sys

from sys import exit
from copy import deepcopy
from vyos.config import Config
from vyos import ConfigError
from vyos.util import call

from vyos import airbag
airbag.enable()

ipv6_disable_file = '/etc/modprobe.d/vyos_disable_ipv6.conf'

default_config_data = {
    'reboot_message': False,
    'ipv6_forward': '1',
    'disable_addr_assignment': False,
    'mp_layer4_hashing': '0',
    'neighbor_cache': 8192,
    'strict_dad': '1'

}

def sysctl(name, value):
    call('sysctl -wq {}={}'.format(name, value))

def get_config(config=None):
    ip_opt = deepcopy(default_config_data)
    if config:
        conf = config
    else:
        conf = Config()
    conf.set_level('system ipv6')
    if conf.exists(''):
        ip_opt['disable_addr_assignment'] = conf.exists('disable')
        if conf.exists_effective('disable') != conf.exists('disable'):
            ip_opt['reboot_message'] = True

        if conf.exists('disable-forwarding'):
            ip_opt['ipv6_forward'] = '0'

        if conf.exists('multipath layer4-hashing'):
            ip_opt['mp_layer4_hashing'] = '1'

        if conf.exists('neighbor table-size'):
            ip_opt['neighbor_cache'] = int(conf.return_value('neighbor table-size'))

        if conf.exists('strict-dad'):
            ip_opt['strict_dad'] = 2

    return ip_opt

def verify(ip_opt):
    pass

def generate(ip_opt):
    pass

def apply(ip_opt):
    # disable IPv6 address assignment
    if ip_opt['disable_addr_assignment']:
        with open(ipv6_disable_file, 'w') as f:
            f.write('options ipv6 disable_ipv6=1')
    else:
        if os.path.exists(ipv6_disable_file):
            os.unlink(ipv6_disable_file)

    if ip_opt['reboot_message']:
        print('Changing IPv6 disable parameter will only take affect\n' \
              'when the system is rebooted.')

    # configure multipath
    sysctl('net.ipv6.fib_multipath_hash_policy', ip_opt['mp_layer4_hashing'])

    # apply neighbor table threshold values
    sysctl('net.ipv6.neigh.default.gc_thresh3', ip_opt['neighbor_cache'])
    sysctl('net.ipv6.neigh.default.gc_thresh2', ip_opt['neighbor_cache'] // 2)
    sysctl('net.ipv6.neigh.default.gc_thresh1', ip_opt['neighbor_cache'] // 8)

    # enable/disable IPv6 forwarding
    with open('/proc/sys/net/ipv6/conf/all/forwarding', 'w') as f:
        f.write(ip_opt['ipv6_forward'])

    # configure IPv6 strict-dad
    for root, dirs, files in os.walk('/proc/sys/net/ipv6/conf'):
        for name in files:
            if name == "accept_dad":
                with open(os.path.join(root, name), 'w') as f:
                    f.write(str(ip_opt['strict_dad']))

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
