#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

from vyos import ConfigError
from vyos.config import Config
from vyos.util import call
from vyos.template import render

from vyos import airbag
airbag.enable()

config_file = r'/tmp/ripd.frr'

def get_config():
    conf = Config()
    base = ['protocols', 'rip']
    rip_conf = {
        'rip_conf'          : False,
        'default_distance'  : [],
        'default_originate' : False,
        'old_rip'  : {
            'default_metric'  : [],
            'distribute'      : {},
            'neighbors'       : {},
            'networks'        : {},
            'net_distance'    : {},
            'passive_iface'   : {},
            'redist'          : {},
            'route'           : {},
            'ifaces'          : {},
            'timer_garbage'   : 120,
            'timer_timeout'   : 180,
            'timer_update'    : 30
        },
        'rip'  : {
            'default_metric'   : None,
            'distribute'       : {},
            'neighbors'        : {},
            'networks'         : {},
            'net_distance'     : {},
            'passive_iface'    : {},
            'redist'           : {},
            'route'            : {},
            'ifaces'           : {},
            'timer_garbage'    : 120,
            'timer_timeout'    : 180,
            'timer_update'     : 30
        }
    }

    if not (conf.exists(base) or conf.exists_effective(base)):
        return None

    if conf.exists(base):
        rip_conf['rip_conf'] = True

    conf.set_level(base)

    # Get default distance
    if conf.exists_effective('default-distance'):
        rip_conf['old_default_distance'] = conf.return_effective_value('default-distance')

    if conf.exists('default-distance'):
        rip_conf['default_distance'] = conf.return_value('default-distance')

    # Get default information originate (originate default route)
    if conf.exists_effective('default-information originate'):
        rip_conf['old_default_originate'] = True

    if conf.exists('default-information originate'):
        rip_conf['default_originate'] = True

    # Get default-metric
    if conf.exists_effective('default-metric'):
        rip_conf['old_rip']['default_metric'] = conf.return_effective_value('default-metric')

    if conf.exists('default-metric'):
        rip_conf['rip']['default_metric'] = conf.return_value('default-metric')

    # Get distribute list interface old_rip
    for dist_iface in conf.list_effective_nodes('distribute-list interface'):
        # Set level 'distribute-list interface ethX'
        conf.set_level(base + ['distribute-list', 'interface', dist_iface])
        rip_conf['rip']['distribute'].update({
        dist_iface : {
            'iface_access_list_in': conf.return_effective_value('access-list in'.format(dist_iface)),
            'iface_access_list_out': conf.return_effective_value('access-list out'.format(dist_iface)),
            'iface_prefix_list_in': conf.return_effective_value('prefix-list in'.format(dist_iface)),
            'iface_prefix_list_out': conf.return_effective_value('prefix-list out'.format(dist_iface))
            }
        })

        # Access-list in old_rip
        if conf.exists_effective('access-list in'.format(dist_iface)):
            rip_conf['old_rip']['iface_access_list_in'] = conf.return_effective_value('access-list in'.format(dist_iface))
        # Access-list out old_rip
        if conf.exists_effective('access-list out'.format(dist_iface)):
            rip_conf['old_rip']['iface_access_list_out'] = conf.return_effective_value('access-list out'.format(dist_iface))
        # Prefix-list in old_rip
        if conf.exists_effective('prefix-list in'.format(dist_iface)):
            rip_conf['old_rip']['iface_prefix_list_in'] = conf.return_effective_value('prefix-list in'.format(dist_iface))
        # Prefix-list out old_rip
        if conf.exists_effective('prefix-list out'.format(dist_iface)):
            rip_conf['old_rip']['iface_prefix_list_out'] = conf.return_effective_value('prefix-list out'.format(dist_iface))

    conf.set_level(base)

    # Get distribute list interface 
    for dist_iface in conf.list_nodes('distribute-list interface'):
        # Set level 'distribute-list interface ethX'
        conf.set_level(base + ['distribute-list', 'interface', dist_iface])
        rip_conf['rip']['distribute'].update({
        dist_iface : {
            'iface_access_list_in': conf.return_value('access-list in'.format(dist_iface)),
            'iface_access_list_out': conf.return_value('access-list out'.format(dist_iface)),
            'iface_prefix_list_in': conf.return_value('prefix-list in'.format(dist_iface)),
            'iface_prefix_list_out': conf.return_value('prefix-list out'.format(dist_iface))
            }
        })

        # Access-list in
        if conf.exists('access-list in'.format(dist_iface)):
            rip_conf['rip']['iface_access_list_in'] = conf.return_value('access-list in'.format(dist_iface))
        # Access-list out
        if conf.exists('access-list out'.format(dist_iface)):
            rip_conf['rip']['iface_access_list_out'] = conf.return_value('access-list out'.format(dist_iface))
        # Prefix-list in
        if conf.exists('prefix-list in'.format(dist_iface)):
            rip_conf['rip']['iface_prefix_list_in'] = conf.return_value('prefix-list in'.format(dist_iface))
        # Prefix-list out
        if conf.exists('prefix-list out'.format(dist_iface)):
            rip_conf['rip']['iface_prefix_list_out'] = conf.return_value('prefix-list out'.format(dist_iface))

    conf.set_level(base + ['distribute-list'])

    # Get distribute list, access-list in
    if conf.exists_effective('access-list in'):
        rip_conf['old_rip']['dist_acl_in'] = conf.return_effective_value('access-list in')

    if conf.exists('access-list in'):
        rip_conf['rip']['dist_acl_in'] = conf.return_value('access-list in')

    # Get distribute list, access-list out
    if conf.exists_effective('access-list out'):
        rip_conf['old_rip']['dist_acl_out'] = conf.return_effective_value('access-list out')

    if conf.exists('access-list out'):
        rip_conf['rip']['dist_acl_out'] = conf.return_value('access-list out')

    # Get ditstribute list, prefix-list in
    if conf.exists_effective('prefix-list in'):
        rip_conf['old_rip']['dist_prfx_in'] = conf.return_effective_value('prefix-list in')

    if conf.exists('prefix-list in'):
        rip_conf['rip']['dist_prfx_in'] = conf.return_value('prefix-list in')

    # Get distribute list, prefix-list out
    if conf.exists_effective('prefix-list out'):
        rip_conf['old_rip']['dist_prfx_out'] = conf.return_effective_value('prefix-list out')

    if conf.exists('prefix-list out'):
        rip_conf['rip']['dist_prfx_out'] = conf.return_value('prefix-list out')

    conf.set_level(base)

    # Get network Interfaces
    if conf.exists_effective('interface'):
        rip_conf['old_rip']['ifaces'] = conf.return_effective_values('interface')

    if conf.exists('interface'):
        rip_conf['rip']['ifaces'] = conf.return_values('interface')

    # Get neighbors
    if conf.exists_effective('neighbor'):
        rip_conf['old_rip']['neighbors'] = conf.return_effective_values('neighbor')

    if conf.exists('neighbor'):
        rip_conf['rip']['neighbors'] = conf.return_values('neighbor')

    # Get networks
    if conf.exists_effective('network'):
        rip_conf['old_rip']['networks'] = conf.return_effective_values('network')

    if conf.exists('network'):
        rip_conf['rip']['networks'] = conf.return_values('network')

    # Get network-distance old_rip
    for net_dist in conf.list_effective_nodes('network-distance'):
        rip_conf['old_rip']['net_distance'].update({
            net_dist : {
                'access_list' : conf.return_effective_value('network-distance {0} access-list'.format(net_dist)),
                'distance' : conf.return_effective_value('network-distance {0} distance'.format(net_dist)),
            }
        })

    # Get network-distance
    for net_dist in conf.list_nodes('network-distance'):
        rip_conf['rip']['net_distance'].update({
            net_dist : {
                'access_list' : conf.return_value('network-distance {0} access-list'.format(net_dist)),
                'distance' : conf.return_value('network-distance {0} distance'.format(net_dist)),
            }
        })

    # Get passive-interface
    if conf.exists_effective('passive-interface'):
        rip_conf['old_rip']['passive_iface'] = conf.return_effective_values('passive-interface')

    if conf.exists('passive-interface'):
        rip_conf['rip']['passive_iface'] = conf.return_values('passive-interface')

    # Get redistribute for old_rip
    for protocol in conf.list_effective_nodes('redistribute'):
        rip_conf['old_rip']['redist'].update({
            protocol : {
                'metric' : conf.return_effective_value('redistribute {0} metric'.format(protocol)),
                'route_map' : conf.return_effective_value('redistribute {0} route-map'.format(protocol)),
            }
        })

    # Get redistribute
    for protocol in conf.list_nodes('redistribute'):
        rip_conf['rip']['redist'].update({
            protocol : {
                'metric' : conf.return_value('redistribute {0} metric'.format(protocol)),
                'route_map' : conf.return_value('redistribute {0} route-map'.format(protocol)),
            }
        })

    conf.set_level(base)

    # Get route
    if conf.exists_effective('route'):
        rip_conf['old_rip']['route'] = conf.return_effective_values('route')

    if conf.exists('route'):
        rip_conf['rip']['route'] = conf.return_values('route')

    # Get timers garbage
    if conf.exists_effective('timers garbage-collection'):
        rip_conf['old_rip']['timer_garbage'] = conf.return_effective_value('timers garbage-collection')

    if conf.exists('timers garbage-collection'):
        rip_conf['rip']['timer_garbage'] = conf.return_value('timers garbage-collection')

    # Get timers timeout
    if conf.exists_effective('timers timeout'):
        rip_conf['old_rip']['timer_timeout'] = conf.return_effective_value('timers timeout')

    if conf.exists('timers timeout'):
        rip_conf['rip']['timer_timeout'] = conf.return_value('timers timeout')

    # Get timers update
    if conf.exists_effective('timers update'):
        rip_conf['old_rip']['timer_update'] = conf.return_effective_value('timers update')

    if conf.exists('timers update'):
        rip_conf['rip']['timer_update'] = conf.return_value('timers update')

    return rip_conf

def verify(rip):
    if rip is None:
        return None

    # Check for network. If network-distance acl is set and distance not set
    for net in rip['rip']['net_distance']:
        if not rip['rip']['net_distance'][net]['distance']:
            raise ConfigError(f"Must specify distance for network {net}")

def generate(rip):
    if rip is None:
        return None

    render(config_file, 'frr/rip.frr.tmpl', rip)
    return None

def apply(rip):
    if rip is None:
        return None

    if os.path.exists(config_file):
        call(f'vtysh -d ripd -f {config_file}')
        os.remove(config_file)
    else:
        print("File {0} not found".format(config_file))


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

