#!/usr/bin/env python3
#
# Copyright (C) 2019-2023 VyOS maintainers and contributors
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
from vyos.configdict import dict_merge
from vyos.configverify import verify_route_map
from vyos.template import render_to_string
from vyos.utils.dict import dict_search
from vyos.utils.file import write_file
from vyos.utils.process import is_systemd_service_active
from vyos.utils.system import sysctl_write
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'ipv6']

    opt = conf.get_config_dict(base, key_mangling=('-', '_'),
                               get_first_key=True,
                               with_recursive_defaults=True)

    # When working with FRR we need to know the corresponding address-family
    opt['afi'] = 'ipv6'

    # We also need the route-map information from the config
    #
    # XXX: one MUST always call this without the key_mangling() option! See
    # vyos.configverify.verify_common_route_maps() for more information.
    tmp = {'policy' : {'route-map' : conf.get_config_dict(['policy', 'route-map'],
                                                          get_first_key=True)}}
    # Merge policy dict into "regular" config dict
    opt = dict_merge(tmp, opt)
    return opt

def verify(opt):
    if 'protocol' in opt:
        for protocol, protocol_options in opt['protocol'].items():
            if 'route_map' in protocol_options:
                verify_route_map(protocol_options['route_map'], opt)
    return

def generate(opt):
    opt['frr_zebra_config'] = render_to_string('frr/zebra.route-map.frr.j2', opt)
    return

def apply(opt):
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

    # enable/disable IPv6 forwarding
    tmp = dict_search('disable_forwarding', opt)
    value = '0' if (tmp != None) else '1'
    write_file('/proc/sys/net/ipv6/conf/all/forwarding', value)

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
        zebra_daemon = 'zebra'
        # Save original configuration prior to starting any commit actions
        frr_cfg = frr.FRRConfig()

        # The route-map used for the FIB (zebra) is part of the zebra daemon
        frr_cfg.load_configuration(zebra_daemon)
        frr_cfg.modify_section(r'no ipv6 nht resolve-via-default')
        frr_cfg.modify_section(r'ipv6 protocol \w+ route-map [-a-zA-Z0-9.]+', stop_pattern='(\s|!)')
        if 'frr_zebra_config' in opt:
            frr_cfg.add_before(frr.default_add_before, opt['frr_zebra_config'])
        frr_cfg.commit_configuration(zebra_daemon)

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
