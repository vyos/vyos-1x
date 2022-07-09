#!/usr/bin/env python3
#
# Copyright (C) 2019-2022 VyOS maintainers and contributors
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

from sys import exit

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.util import call
from vyos.util import dict_search
from vyos.util import sysctl_write
from vyos.util import write_file
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'ip']

    opt = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)
    opt = dict_merge(default_values, opt)

    return opt

def verify(opt):
    pass

def generate(opt):
    pass

def apply(opt):
    # Apply ARP threshold values
    # table_size has a default value - thus the key always exists
    size = int(dict_search('arp.table_size', opt))
    # Amount upon reaching which the records begin to be cleared immediately
    sysctl_write('net.ipv4.neigh.default.gc_thresh3', size)
    # Amount after which the records begin to be cleaned after 5 seconds
    sysctl_write('net.ipv4.neigh.default.gc_thresh2', size // 2)
    # Minimum number of stored records is indicated which is not cleared
    sysctl_write('net.ipv4.neigh.default.gc_thresh1', size // 8)

    # enable/disable IPv4 forwarding
    tmp = dict_search('disable_forwarding', opt)
    value = '0' if (tmp != None) else '1'
    write_file('/proc/sys/net/ipv4/conf/all/forwarding', value)

    # enable/disable IPv4 directed broadcast forwarding
    tmp = dict_search('disable_directed_broadcast', opt)
    value = '0' if (tmp != None) else '1'
    write_file('/proc/sys/net/ipv4/conf/all/bc_forwarding', value)

    # configure multipath
    tmp = dict_search('multipath.ignore_unreachable_nexthops', opt)
    value = '1' if (tmp != None) else '0'
    sysctl_write('net.ipv4.fib_multipath_use_neigh', value)

    tmp = dict_search('multipath.layer4_hashing', opt)
    value = '1' if (tmp != None) else '0'
    sysctl_write('net.ipv4.fib_multipath_hash_policy', value)

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
