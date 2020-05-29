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
from netifaces import interfaces

from vyos.config import Config
from vyos.configdict import dhcpv6_pd_default_data
from vyos.ifconfig import Interface
from vyos.template import render
from vyos.util import chown, chmod_755, call
from vyos import ConfigError

from vyos import airbag
airbag.enable()

default_config_data = {
    **dhcpv6_pd_default_data,
    'access_concentrator': '',
    'auth_username': '',
    'auth_password': '',
    'on_demand': False,
    'default_route': 'auto',
    'deleted': False,
    'description': '\0',
    'disable': False,
    'intf': '',
    'idle_timeout': '',
    'ipv6_autoconf': False,
    'ipv6_enable': False,
    'local_address': '',
    'mtu': '1492',
    'name_server': True,
    'remote_address': '',
    'service_name': '',
    'source_interface': '',
    'vrf': ''
}

def get_config():
    pppoe = deepcopy(default_config_data)
    conf = Config()
    base_path = ['interfaces', 'pppoe']

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    pppoe['intf'] = os.environ['VYOS_TAGNODE_VALUE']

    # Check if interface has been removed
    if not conf.exists(base_path + [pppoe['intf']]):
        pppoe['deleted'] = True
        return pppoe

    # set new configuration level
    conf.set_level(base_path + [pppoe['intf']])

    # Access concentrator name (only connect to this concentrator)
    if conf.exists(['access-concentrator']):
        pppoe['access_concentrator'] = conf.return_values(['access-concentrator'])

    # Authentication name supplied to PPPoE server
    if conf.exists(['authentication', 'user']):
        pppoe['auth_username'] = conf.return_value(['authentication', 'user'])

    # Password for authenticating local machine to PPPoE server
    if conf.exists(['authentication', 'password']):
        pppoe['auth_password'] = conf.return_value(['authentication', 'password'])

    # Access concentrator name (only connect to this concentrator)
    if conf.exists(['connect-on-demand']):
        pppoe['on_demand'] = True

    # Enable/Disable default route to peer when link comes up
    if conf.exists(['default-route']):
        pppoe['default_route'] = conf.return_value(['default-route'])

    # Retrieve interface description
    if conf.exists(['description']):
        pppoe['description'] = conf.return_value(['description'])

    # Disable this interface
    if conf.exists(['disable']):
        pppoe['disable'] = True

    # Delay before disconnecting idle session (in seconds)
    if conf.exists(['idle-timeout']):
        pppoe['idle_timeout'] = conf.return_value(['idle-timeout'])

    # Enable Stateless Address Autoconfiguration (SLAAC)
    if conf.exists(['ipv6', 'address', 'autoconf']):
        pppoe['ipv6_autoconf'] = True

    # Activate IPv6 support on this connection
    if conf.exists(['ipv6', 'enable']):
        pppoe['ipv6_enable'] = True

    # IPv4 address of local end of PPPoE link
    if conf.exists(['local-address']):
        pppoe['local_address'] = conf.return_value(['local-address'])

    # Physical Interface used for this PPPoE session
    if conf.exists(['source-interface']):
        pppoe['source_interface'] = conf.return_value(['source-interface'])

    # Maximum Transmission Unit (MTU)
    if conf.exists(['mtu']):
        pppoe['mtu'] = conf.return_value(['mtu'])

    # Do not use DNS servers provided by the peer
    if conf.exists(['no-peer-dns']):
        pppoe['name_server'] = False

    # IPv4 address for remote end of PPPoE session
    if conf.exists(['remote-address']):
        pppoe['remote_address'] = conf.return_value(['remote-address'])

    # Service name, only connect to access concentrators advertising this
    if conf.exists(['service-name']):
        pppoe['service_name'] = conf.return_value(['service-name'])

    # retrieve VRF instance
    if conf.exists('vrf'):
        pppoe['vrf'] = conf.return_value(['vrf'])

    if conf.exists(['dhcpv6-options', 'prefix-delegation']):
        dhcpv6_pd_path = base_path + [pppoe['intf'],
                                      'dhcpv6-options', 'prefix-delegation']
        conf.set_level(dhcpv6_pd_path)

        # retriebe DHCPv6-PD prefix helper length as some ISPs only hand out a
        # /64 by default (https://phabricator.vyos.net/T2506)
        if conf.exists(['length']):
            pppoe['dhcpv6_pd_length'] = conf.return_value(['length'])

        for interface in conf.list_nodes(['interface']):
            conf.set_level(dhcpv6_pd_path + ['interface', interface])
            pd = {
                'ifname': interface,
                'sla_id': '',
                'sla_len': '',
                'if_id': ''
            }

            if conf.exists(['sla-id']):
                pd['sla_id'] = conf.return_value(['sla-id'])

            if conf.exists(['sla-len']):
                pd['sla_len'] = conf.return_value(['sla-len'])

            if conf.exists(['address']):
                pd['if_id'] = conf.return_value(['address'])

            pppoe['dhcpv6_pd_interfaces'].append(pd)

    return pppoe

def verify(pppoe):
    if pppoe['deleted']:
        # bail out early
        return None

    if not pppoe['source_interface']:
        raise ConfigError('PPPoE source interface missing')

    if not pppoe['source_interface'] in interfaces():
        raise ConfigError(f"PPPoE source interface {pppoe['source_interface']} does not exist")

    vrf_name = pppoe['vrf']
    if vrf_name and vrf_name not in interfaces():
        raise ConfigError(f'VRF {vrf_name} does not exist')

    if pppoe['on_demand'] and pppoe['vrf']:
        raise ConfigError('On-demand dialing and VRF can not be used at the same time')

    return None

def generate(pppoe):
    # set up configuration file path variables where our templates will be
    # rendered into
    intf = pppoe['intf']
    config_pppoe = f'/etc/ppp/peers/{intf}'
    script_pppoe_pre_up = f'/etc/ppp/ip-pre-up.d/1000-vyos-pppoe-{intf}'
    script_pppoe_ip_up = f'/etc/ppp/ip-up.d/1000-vyos-pppoe-{intf}'
    script_pppoe_ip_down = f'/etc/ppp/ip-down.d/1000-vyos-pppoe-{intf}'
    script_pppoe_ipv6_up = f'/etc/ppp/ipv6-up.d/1000-vyos-pppoe-{intf}'
    config_wide_dhcp6c = f'/run/dhcp6c/dhcp6c.{intf}.conf'

    config_files = [config_pppoe, script_pppoe_pre_up, script_pppoe_ip_up,
                    script_pppoe_ip_down, script_pppoe_ipv6_up, config_wide_dhcp6c]

    if pppoe['deleted']:
        # stop DHCPv6-PD client
        call(f'systemctl stop dhcp6c@{intf}.service')
        # Hang-up PPPoE connection
        call(f'systemctl stop ppp@{intf}.service')

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

    if len(pppoe['dhcpv6_pd_interfaces']) > 0:
        # ipv6.tmpl relies on ifname - this should be made consitent in the
        # future better then double key-ing the same value
        pppoe['ifname'] = intf
        render(config_wide_dhcp6c, 'dhcp-client/ipv6.tmpl', pppoe, trim_blocks=True)

    return None

def apply(pppoe):
    if pppoe['deleted']:
        # bail out early
        return None

    if not pppoe['disable']:
        # Dial PPPoE connection
        call('systemctl restart ppp@{intf}.service'.format(**pppoe))

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
