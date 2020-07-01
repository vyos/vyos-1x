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
import jmespath

from sys import exit
from copy import deepcopy
from netifaces import interfaces

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configverify import verify_source_interface
from vyos.configverify import verify_vrf
from vyos.template import render
from vyos.util import call
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config():
    """ Retrive CLI config as dictionary. Dictionary can never be empty,
    as at least the interface name will be added or a deleted flag """
    conf = Config()

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    # retrieve interface default values
    base = ['interfaces', 'pppoe']
    default_values = defaults(base)
    # PPPoE is "special" the default MTU is 1492 - update accordingly
    default_values['mtu'] = '1492'

    ifname = os.environ['VYOS_TAGNODE_VALUE']
    base = base + [ifname]

    pppoe = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    # Check if interface has been removed
    if pppoe == {}:
        pppoe.update({'deleted' : ''})

    # We have gathered the dict representation of the CLI, but there are
    # default options which we need to update into the dictionary
    # retrived.
    pppoe = dict_merge(default_values, pppoe)

    # Add interface instance name into dictionary
    pppoe.update({'ifname': ifname})

    return pppoe

def verify(pppoe):
    if 'deleted' in pppoe.keys():
        # bail out early
        return None

    verify_source_interface(pppoe)
    verify_vrf(pppoe)

    if {'connect_on_demand', 'vrf'} <= set(pppoe):
        raise ConfigError('On-demand dialing and VRF can not be used at the same time')

    return None

def generate(pppoe):
    # set up configuration file path variables where our templates will be
    # rendered into
    ifname = pppoe['ifname']
    config_pppoe = f'/etc/ppp/peers/{ifname}'
    script_pppoe_pre_up = f'/etc/ppp/ip-pre-up.d/1000-vyos-pppoe-{ifname}'
    script_pppoe_ip_up = f'/etc/ppp/ip-up.d/1000-vyos-pppoe-{ifname}'
    script_pppoe_ip_down = f'/etc/ppp/ip-down.d/1000-vyos-pppoe-{ifname}'
    script_pppoe_ipv6_up = f'/etc/ppp/ipv6-up.d/1000-vyos-pppoe-{ifname}'
    config_wide_dhcp6c = f'/run/dhcp6c/dhcp6c.{ifname}.conf'

    config_files = [config_pppoe, script_pppoe_pre_up, script_pppoe_ip_up,
                    script_pppoe_ip_down, script_pppoe_ipv6_up, config_wide_dhcp6c]

    if 'deleted' in pppoe.keys():
        # stop DHCPv6-PD client
        call(f'systemctl stop dhcp6c@{ifname}.service')
        # Hang-up PPPoE connection
        call(f'systemctl stop ppp@{ifname}.service')

        # Delete PPP configuration files
        for file in config_files:
            if os.path.exists(file):
                os.unlink(file)

        return None

    # Create PPP configuration files
    render(config_pppoe, 'pppoe/peer.tmpl',
           pppoe, trim_blocks=True, permission=0o755)
    # Create script for ip-pre-up.d
    render(script_pppoe_pre_up, 'pppoe/ip-pre-up.script.tmpl',
           pppoe, trim_blocks=True, permission=0o755)
    # Create script for ip-up.d
    render(script_pppoe_ip_up, 'pppoe/ip-up.script.tmpl',
           pppoe, trim_blocks=True, permission=0o755)
    # Create script for ip-down.d
    render(script_pppoe_ip_down, 'pppoe/ip-down.script.tmpl',
           pppoe, trim_blocks=True, permission=0o755)
    # Create script for ipv6-up.d
    render(script_pppoe_ipv6_up, 'pppoe/ipv6-up.script.tmpl',
           pppoe, trim_blocks=True, permission=0o755)

    tmp = jmespath.search('dhcpv6_options.prefix_delegation.interface', pppoe)
    if tmp and len(tmp) > 0:
        # ipv6.tmpl relies on ifname - this should be made consitent in the
        # future better then double key-ing the same value
        render(config_wide_dhcp6c, 'dhcp-client/ipv6_new.tmpl', pppoe, trim_blocks=True)

    return None

def apply(pppoe):
    if 'deleted' in pppoe.keys():
        # bail out early
        return None

    if 'disable' not in pppoe.keys():
        # Dial PPPoE connection
        call('systemctl restart ppp@{ifname}.service'.format(**pppoe))

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
