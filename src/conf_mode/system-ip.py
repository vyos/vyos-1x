#!/usr/bin/env python3
#
# Copyright (C) 2019-2020 VyOS maintainers and contributors
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
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def sysctl(name, value):
    call(f'sysctl -wq {name}={value}')

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
    size = int(dict_search('arp.table_size', opt))
    if size:
        # apply ARP threshold values
        sysctl('net.ipv4.neigh.default.gc_thresh3', str(size))
        sysctl('net.ipv4.neigh.default.gc_thresh2', str(size // 2))
        sysctl('net.ipv4.neigh.default.gc_thresh1', str(size // 8))

    # enable/disable IPv4 forwarding
    tmp = '1'
    if 'disable_forwarding' in opt:
        tmp = '0'
    sysctl('net.ipv4.conf.all.forwarding', tmp)

    tmp = '0'
    # configure multipath - dict_search() returns an empty dict if key was found
    if isinstance(dict_search('multipath.ignore_unreachable_nexthops', opt), dict):
        tmp = '1'
    sysctl('net.ipv4.fib_multipath_use_neigh', tmp)

    tmp = '0'
    if isinstance(dict_search('multipath.ignore_unreachable_nexthops', opt), dict):
        tmp = '1'
    sysctl('net.ipv4.fib_multipath_hash_policy', tmp)

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
