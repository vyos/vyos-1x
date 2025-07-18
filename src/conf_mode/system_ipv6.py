#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
from vyos.config import Config
from vyos.configdep import set_dependents
from vyos.configdep import call_dependents
from vyos.configverify import has_frr_protocol_in_dict
from vyos.configverify import verify_route_map
from vyos.frrender import FRRender
from vyos.frrender import get_frrender_dict
from vyos.utils.dict import dict_search
from vyos.utils.file import write_file
from vyos.utils.process import is_systemd_service_active
from vyos.utils.process import is_systemd_service_running
from vyos.utils.system import sysctl_write
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    # If IPv6 neighbor table size is set here and also manually in sysctl, the more
    # fine grained value from sysctl must win
    set_dependents('sysctl', conf)
    return get_frrender_dict(conf)

def verify(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'ipv6'):
        return None

    opt = config_dict['ipv6']
    opt['policy'] = config_dict['policy']

    if 'protocol' in opt:
        for protocol, protocol_options in opt['protocol'].items():
            if 'route_map' in protocol_options:
                verify_route_map(protocol_options['route_map'], opt)
    return

def generate(config_dict):
    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().generate(config_dict)
    return None

def apply(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'ipv6'):
        return None
    opt = config_dict['ipv6']

    # configure multipath
    tmp = dict_search('multipath.layer4_hashing', opt)
    value = '1' if (tmp != None) else '0'
    sysctl_write('net.ipv6.fib_multipath_hash_policy', value)

    # Apply ND threshold values
    # table_size has a default value - thus the key always exists
    size = int(dict_search('neighbor.table_size', opt))
    # Amount upon reaching which the records begin to be cleared immediately
    sysctl_write('net.ipv6.neigh.default.gc_thresh3', size)
    # Amount after which the records begin to be cleaned after 5 seconds
    sysctl_write('net.ipv6.neigh.default.gc_thresh2', size // 2)
    # Minimum number of stored records is indicated which is not cleared
    sysctl_write('net.ipv6.neigh.default.gc_thresh1', size // 8)

    # configure IPv6 strict-dad
    tmp = dict_search('strict_dad', opt)
    value = '2' if (tmp != None) else '1'
    for root, dirs, files in os.walk('/proc/sys/net/ipv6/conf'):
        for name in files:
            if name == 'accept_dad':
                write_file(os.path.join(root, name), value)

    # During startup of vyos-router that brings up FRR, the service is not yet
    # running when this script is called first. Skip this part and wait for initial
    # commit of the configuration to trigger this statement
    if is_systemd_service_active('frr.service'):
        if config_dict and not is_systemd_service_running('vyos-configd.service'):
            FRRender().apply()

    call_dependents()
    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
