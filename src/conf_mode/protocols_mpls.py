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

import os

from vyos.config import Config
from vyos import ConfigError
from vyos.util import call
from vyos.template import render

from vyos import airbag
airbag.enable()

config_file = r'/tmp/ldpd.frr'

def sysctl(name, value):
    call('sysctl -wq {}={}'.format(name, value))

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    mpls_conf = {
        'router_id'  : None,
        'mpls_ldp'   : False,
        'old_parameters' : {
                'no_ttl_propagation'          : False,
                'maximum_ttl'                 : None
        },
        'parameters' : {
                'no_ttl_propagation'          : False,
                'maximum_ttl'                 : None
        },
        'old_ldp'    : {
                'interfaces'                  : [],
                'neighbors'                   : {},
                'd_transp_ipv4'               : None,
                'd_transp_ipv6'               : None,
                'hello_ipv4_holdtime'         : None,
                'hello_ipv4_interval'         : None,
                'hello_ipv6_holdtime'         : None,
                'hello_ipv6_interval'         : None,
                'ses_ipv4_hold'               : None,
                'ses_ipv6_hold'               : None,
                'export_ipv4_exp'             : False,
                'export_ipv6_exp'             : False,
                'cisco_interop_tlv'           : False,
                'transport_prefer_ipv4'       : False,
                'target_ipv4_addresses'       : [],
                'target_ipv6_addresses'       : [],
                'target_ipv4_enable'          : False,
                'target_ipv6_enable'          : False,
                'target_ipv4_hello_int'       : None,
                'target_ipv6_hello_int'       : None,
                'target_ipv4_hello_hold'      : None,
                'target_ipv6_hello_hold'      : None
        },
        'ldp'        : {
                'interfaces'                  : [],
                'neighbors'                   : {},
                'd_transp_ipv4'               : None,
                'd_transp_ipv6'               : None,
                'hello_ipv4_holdtime'         : None,
                'hello_ipv4_interval'         : None,
                'hello_ipv6_holdtime'         : None,
                'hello_ipv6_interval'         : None,
                'ses_ipv4_hold'               : None,
                'ses_ipv6_hold'               : None,
                'export_ipv4_exp'             : False,
                'export_ipv6_exp'             : False,
                'cisco_interop_tlv'           : False,
                'transport_prefer_ipv4'       : False,
                'target_ipv4_addresses'       : [],
                'target_ipv6_addresses'       : [],
                'target_ipv4_enable'          : False,
                'target_ipv6_enable'          : False,
                'target_ipv4_hello_int'       : None,
                'target_ipv6_hello_int'       : None,
                'target_ipv4_hello_hold'      : None,
                'target_ipv6_hello_hold'      : None
        }
    }
    if not (conf.exists('protocols mpls') or conf.exists_effective('protocols mpls')):
        return None
    
    # If LDP is defined then enable LDP portion of code
    if conf.exists('protocols mpls ldp'):
        mpls_conf['mpls_ldp'] = True

    # Set to MPLS hierarchy configuration level
    conf.set_level('protocols mpls')
        
    # Get no_ttl_propagation
    if conf.exists_effective('parameters no-propagate-ttl'):
        mpls_conf['old_parameters']['no_ttl_propagation'] = True

    if conf.exists('parameters no-propagate-ttl'):
        mpls_conf['parameters']['no_ttl_propagation'] = True

    # Get maximum_ttl
    if conf.exists_effective('parameters maximum-ttl'):
        mpls_conf['old_parameters']['maximum_ttl'] = conf.return_effective_value('parameters maximum-ttl')

    if conf.exists('parameters maximum-ttl'):
        mpls_conf['parameters']['maximum_ttl'] = conf.return_value('parameters maximum-ttl')

    # Set to LDP hierarchy configuration level
    conf.set_level('protocols mpls ldp')

    # Get router-id
    if conf.exists_effective('router-id'):
        mpls_conf['old_router_id'] = conf.return_effective_value('router-id')
        
    if conf.exists('router-id'):
        mpls_conf['router_id'] = conf.return_value('router-id')

    # Get hello-ipv4-holdtime
    if conf.exists_effective('discovery hello-ipv4-holdtime'):
        mpls_conf['old_ldp']['hello_ipv4_holdtime'] = conf.return_effective_value('discovery hello-ipv4-holdtime')

    if conf.exists('discovery hello-ipv4-holdtime'):
        mpls_conf['ldp']['hello_ipv4_holdtime'] = conf.return_value('discovery hello-ipv4-holdtime')

    # Get hello-ipv4-interval
    if conf.exists_effective('discovery hello-ipv4-interval'):
        mpls_conf['old_ldp']['hello_ipv4_interval'] = conf.return_effective_value('discovery hello-ipv4-interval')

    if conf.exists('discovery hello-ipv4-interval'):
        mpls_conf['ldp']['hello_ipv4_interval'] = conf.return_value('discovery hello-ipv4-interval')
        
    # Get hello-ipv6-holdtime
    if conf.exists_effective('discovery hello-ipv6-holdtime'):
        mpls_conf['old_ldp']['hello_ipv6_holdtime'] = conf.return_effective_value('discovery hello-ipv6-holdtime')

    if conf.exists('discovery hello-ipv6-holdtime'):
        mpls_conf['ldp']['hello_ipv6_holdtime'] = conf.return_value('discovery hello-ipv6-holdtime')

    # Get hello-ipv6-interval
    if conf.exists_effective('discovery hello-ipv6-interval'):
        mpls_conf['old_ldp']['hello_ipv6_interval'] = conf.return_effective_value('discovery hello-ipv6-interval')

    if conf.exists('discovery hello-ipv6-interval'):
        mpls_conf['ldp']['hello_ipv6_interval'] = conf.return_value('discovery hello-ipv6-interval')

    # Get session-ipv4-holdtime
    if conf.exists_effective('discovery session-ipv4-holdtime'):
        mpls_conf['old_ldp']['ses_ipv4_hold'] = conf.return_effective_value('discovery session-ipv4-holdtime')

    if conf.exists('discovery session-ipv4-holdtime'):
        mpls_conf['ldp']['ses_ipv4_hold'] = conf.return_value('discovery session-ipv4-holdtime')

    # Get session-ipv6-holdtime
    if conf.exists_effective('discovery session-ipv6-holdtime'):
        mpls_conf['old_ldp']['ses_ipv6_hold'] = conf.return_effective_value('discovery session-ipv6-holdtime')

    if conf.exists('discovery session-ipv6-holdtime'):
        mpls_conf['ldp']['ses_ipv6_hold'] = conf.return_value('discovery session-ipv6-holdtime')

    # Get discovery transport-ipv4-address
    if conf.exists_effective('discovery transport-ipv4-address'):
        mpls_conf['old_ldp']['d_transp_ipv4'] = conf.return_effective_value('discovery transport-ipv4-address')

    if conf.exists('discovery transport-ipv4-address'):
        mpls_conf['ldp']['d_transp_ipv4'] = conf.return_value('discovery transport-ipv4-address')

    # Get discovery transport-ipv6-address
    if conf.exists_effective('discovery transport-ipv6-address'):
        mpls_conf['old_ldp']['d_transp_ipv6'] = conf.return_effective_value('discovery transport-ipv6-address')

    if conf.exists('discovery transport-ipv6-address'):
        mpls_conf['ldp']['d_transp_ipv6'] = conf.return_value('discovery transport-ipv6-address')

    # Get export ipv4 explicit-null
    if conf.exists_effective('export ipv4 explicit-null'):
        mpls_conf['old_ldp']['export_ipv4_exp'] = True

    if conf.exists('export ipv4 explicit-null'):
        mpls_conf['ldp']['export_ipv4_exp'] = True

    # Get export ipv6 explicit-null
    if conf.exists_effective('export ipv6 explicit-null'):
        mpls_conf['old_ldp']['export_ipv6_exp'] = True

    if conf.exists('export ipv6 explicit-null'):
        mpls_conf['ldp']['export_ipv6_exp'] = True

    # Get target_ipv4_addresses
    if conf.exists_effective('targeted-neighbor ipv4 address'):
        mpls_conf['old_ldp']['target_ipv4_addresses'] = conf.return_effective_values('targeted-neighbor ipv4 address')

    if conf.exists('targeted-neighbor ipv4 address'):
        mpls_conf['ldp']['target_ipv4_addresses'] = conf.return_values('targeted-neighbor ipv4 address')

    # Get target_ipv4_enable
    if conf.exists_effective('targeted-neighbor ipv4 enable'):
        mpls_conf['old_ldp']['target_ipv4_enable'] = True

    if conf.exists('targeted-neighbor ipv4 enable'):
        mpls_conf['ldp']['target_ipv4_enable'] = True

    # Get target_ipv4_hello_int
    if conf.exists_effective('targeted-neighbor ipv4 hello-interval'):
        mpls_conf['old_ldp']['target_ipv4_hello_int'] = conf.return_effective_value('targeted-neighbor ipv4 hello-interval')

    if conf.exists('targeted-neighbor ipv4 hello-interval'):
        mpls_conf['ldp']['target_ipv4_hello_int'] = conf.return_value('targeted-neighbor ipv4 hello-interval')

    # Get target_ipv4_hello_hold
    if conf.exists_effective('targeted-neighbor ipv4 hello-holdtime'):
        mpls_conf['old_ldp']['target_ipv4_hello_hold'] = conf.return_effective_value('targeted-neighbor ipv4 hello-holdtime')

    if conf.exists('targeted-neighbor ipv4 hello-holdtime'):
        mpls_conf['ldp']['target_ipv4_hello_hold'] = conf.return_value('targeted-neighbor ipv4 hello-holdtime')

    # Get target_ipv6_addresses
    if conf.exists_effective('targeted-neighbor ipv6 address'):
        mpls_conf['old_ldp']['target_ipv6_addresses'] = conf.return_effective_values('targeted-neighbor ipv6 address')

    if conf.exists('targeted-neighbor ipv6 address'):
       mpls_conf['ldp']['target_ipv6_addresses'] = conf.return_values('targeted-neighbor ipv6 address')

    # Get target_ipv6_enable
    if conf.exists_effective('targeted-neighbor ipv6 enable'):
        mpls_conf['old_ldp']['target_ipv6_enable'] = True

    if conf.exists('targeted-neighbor ipv6 enable'):
        mpls_conf['ldp']['target_ipv6_enable'] = True

    # Get target_ipv6_hello_int
    if conf.exists_effective('targeted-neighbor ipv6 hello-interval'):
        mpls_conf['old_ldp']['target_ipv6_hello_int'] = conf.return_effective_value('targeted-neighbor ipv6 hello-interval')

    if conf.exists('targeted-neighbor ipv6 hello-interval'):
        mpls_conf['ldp']['target_ipv6_hello_int'] = conf.return_value('targeted-neighbor ipv6 hello-interval')

    # Get target_ipv6_hello_hold
    if conf.exists_effective('targeted-neighbor ipv6 hello-holdtime'):
        mpls_conf['old_ldp']['target_ipv6_hello_hold'] = conf.return_effective_value('targeted-neighbor ipv6 hello-holdtime')

    if conf.exists('targeted-neighbor ipv6 hello-holdtime'):
        mpls_conf['ldp']['target_ipv6_hello_hold'] = conf.return_value('targeted-neighbor ipv6 hello-holdtime')

    # Get parameters cisco-interop-tlv
    if conf.exists_effective('parameters cisco-interop-tlv'):
        mpls_conf['old_ldp']['cisco_interop_tlv'] = True

    if conf.exists('parameters cisco-interop-tlv'):
        mpls_conf['ldp']['cisco_interop_tlv'] = True

    # Get parameters transport-prefer-ipv4
    if conf.exists_effective('parameters transport-prefer-ipv4'):
        mpls_conf['old_ldp']['transport_prefer_ipv4'] = True

    if conf.exists('parameters transport-prefer-ipv4'):
        mpls_conf['ldp']['transport_prefer_ipv4'] = True

    # Get interfaces
    if conf.exists_effective('interface'):
        mpls_conf['old_ldp']['interfaces'] = conf.return_effective_values('interface')

    if conf.exists('interface'):
        mpls_conf['ldp']['interfaces'] = conf.return_values('interface')

    # Get neighbors
    for neighbor in conf.list_effective_nodes('neighbor'):
        mpls_conf['old_ldp']['neighbors'].update({
            neighbor : {
                'password' : conf.return_effective_value('neighbor {0} password'.format(neighbor), default=''),
                'ttl_security' : conf.return_effective_value('neighbor {0} ttl-security'.format(neighbor), default=''),
                'session_holdtime' : conf.return_effective_value('neighbor {0} session-holdtime'.format(neighbor), default='')
            }
        })

    for neighbor in conf.list_nodes('neighbor'):
        mpls_conf['ldp']['neighbors'].update({
            neighbor : {
                'password' : conf.return_value('neighbor {0} password'.format(neighbor), default=''),
                'ttl_security' : conf.return_value('neighbor {0} ttl-security'.format(neighbor), default=''),
                'session_holdtime' : conf.return_value('neighbor {0} session-holdtime'.format(neighbor), default='')
            }
        })

    return mpls_conf

def operate_mpls_on_intfc(interfaces, action):
    rp_filter = 0
    if action == 1:
        rp_filter = 2
    for iface in interfaces:
        sysctl('net.mpls.conf.{0}.input'.format(iface), action)
        # Operate rp filter
        sysctl('net.ipv4.conf.{0}.rp_filter'.format(iface), rp_filter)

def verify(mpls):
    if mpls is None:
        return None

    if mpls['mpls_ldp']:
        # Require router-id
        if not mpls['router_id']:
            raise ConfigError(f"MPLS ldp router-id is mandatory!")

        # Require discovery transport-address
        if not mpls['ldp']['d_transp_ipv4'] and not mpls['ldp']['d_transp_ipv6']:
            raise ConfigError(f"MPLS ldp discovery transport address is mandatory!")

        # Require interface
        if not mpls['ldp']['interfaces']:
            raise ConfigError(f"MPLS ldp interface is mandatory!")

def generate(mpls):
    if mpls is None:
        return None

    render(config_file, 'frr/ldpd.frr.tmpl', mpls)
    return None

def apply(mpls):
    if mpls is None:
        return None

    # Set number of entries in the platform label table
    if mpls['mpls_ldp']:
        sysctl('net.mpls.platform_labels', '1048575')
    else:
        sysctl('net.mpls.platform_labels', '0')

    # Choose whether to copy IP TTL to MPLS header TTL
    if mpls['parameters']['no_ttl_propagation']:
        sysctl('net.mpls.ip_ttl_propagate', '0')
    else:
        sysctl('net.mpls.ip_ttl_propagate', '1')
        
    # Choose whether to limit maximum MPLS header TTL
    if mpls['parameters']['maximum_ttl']:
        sysctl('net.mpls.default_ttl', '%s' %(mpls['parameters']['maximum_ttl']))
    else:
        sysctl('net.mpls.default_ttl', '255')    
    
    # Allow mpls on interfaces
    operate_mpls_on_intfc(mpls['ldp']['interfaces'], 1)

    # Disable mpls on deleted interfaces
    diactive_ifaces = set(mpls['old_ldp']['interfaces']).difference(mpls['ldp']['interfaces'])
    operate_mpls_on_intfc(diactive_ifaces, 0)

    if os.path.exists(config_file):
        call(f'vtysh -d ldpd -f {config_file}')
        os.remove(config_file)

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
