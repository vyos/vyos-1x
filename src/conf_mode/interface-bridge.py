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
#
#

import os
import sys
import copy
import subprocess

import vyos.configinterface as VyIfconfig

from vyos.config import Config
from vyos import ConfigError

default_config_data = {
    'address': [],
    'aging': '300',
    'br_name': '',
    'description': '',
    'deleted': False,
    'dhcp_client_id': '',
    'dhcp_hostname': '',
    'dhcpv6_parameters_only': False,
    'dhcpv6_temporary': False,
    'disable': False,
    'disable_link_detect': False,
    'forwarding_delay': '15',
    'hello_time': '2',
    'igmp_querier': 0,
    'arp_cache_timeout_ms': '30000',
    'mac' : '',
    'max_age': '20',
    'member': [],
    'member_remove': [],
    'priority': '32768',
    'stp': 'off'
}

def subprocess_cmd(command):
    process = subprocess.Popen(command,stdout=subprocess.PIPE, shell=True)
    proc_stdout = process.communicate()[0].strip()
    print(proc_stdout)

def diff(first, second):
    second = set(second)
    return [item for item in first if item not in second]

def get_config():
    bridge = copy.deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    try:
        bridge['br_name'] = os.environ['VYOS_TAGNODE_VALUE']
    except KeyError as E:
        print("Interface not specified")

    # Check if bridge has been removed
    if not conf.exists('interfaces bridge ' + bridge['br_name']):
        bridge['deleted'] = True
        return bridge

    # set new configuration level
    conf.set_level('interfaces bridge ' + bridge['br_name'])

    # retrieve configured interface addresses
    if conf.exists('address'):
        bridge['address'] = conf.return_values('address')

    # retrieve aging - how long addresses are retained
    if conf.exists('aging'):
        bridge['aging'] = conf.return_value('aging')

    # retrieve interface description
    if conf.exists('description'):
        bridge['description'] = conf.return_value('description')

    # DHCP client identifier
    if conf.exists('dhcp-options client-id'):
        bridge['dhcp_client_id'] = conf.return_value('dhcp-options client-id')

    # DHCP client hostname
    if conf.exists('dhcp-options host-name'):
        bridge['dhcp_hostname'] = conf.return_value('dhcp-options host-name')

    # DHCPv6 acquire only config parameters, no address
    if conf.exists('dhcpv6-options parameters-only'):
        bridge['dhcpv6_parameters_only'] = True

    # DHCPv6 IPv6 "temporary" address
    if conf.exists('dhcpv6-options temporary'):
        bridge['dhcpv6_temporary'] = True

    # Disable this bridge interface
    if conf.exists('disable'):
        bridge['disable'] = True

    # Ignore link state changes
    if conf.exists('disable-link-detect'):
        bridge['disable_link_detect'] = True

    # Forwarding delay
    if conf.exists('forwarding-delay'):
        bridge['forwarding_delay'] = conf.return_value('forwarding-delay')

    # Hello packet advertisment interval
    if conf.exists('hello-time'):
        bridge['hello_time'] = conf.return_value('hello-time')

    # Enable Internet Group Management Protocol (IGMP) querier
    if conf.exists('igmp querier'):
        bridge['igmp_querier'] = 1

    # ARP cache entry timeout in seconds
    if conf.exists('ip arp-cache-timeout'):
        tmp = 1000 * int(conf.return_value('ip arp-cache-timeout'))
        bridge['arp_cache_timeout_ms'] = str(tmp)

    # Media Access Control (MAC) address
    if conf.exists('mac'):
        bridge['mac'] = conf.return_value('mac')

    # Interval at which neighbor bridges are removed
    if conf.exists('max-age'):
        bridge['max_age'] = conf.return_value('max-age')

    # Determine bridge member interface (currently configured)
    for intf in conf.list_nodes('member interface'):
        iface = {
            'name': intf,
            'cost': '',
            'priority': ''
        }

        if conf.exists('member interface {} cost'.format(intf)):
            iface['cost'] = conf.return_value('member interface {} cost'.format(intf))

        if conf.exists('member interface {} priority'.format(intf)):
            iface['priority'] = conf.return_value('member interface {} priority'.format(intf))

        bridge['member'].append(iface)

    # Determine bridge member interface (currently effective) - to determine which interfaces
    # need to be removed from the bridge
    eff_intf = conf.list_effective_nodes('member interface')
    act_intf = conf.list_nodes('member interface')
    bridge['member_remove'] = diff(eff_intf, act_intf)

    # Priority for this bridge
    if conf.exists('priority'):
        bridge['priority'] = conf.return_value('priority')

    # Enable spanning tree protocol
    if conf.exists('stp'):
        bridge['stp'] = 'on'

    return bridge

def verify(bridge):
    if bridge is None:
        return None

    conf = Config()
    for br in conf.list_nodes('interfaces bridge'):
        # it makes no sense to verify ourself in this case
        if br == bridge['br_name']:
            continue

        for intf in bridge['member']:
            tmp = conf.list_nodes('interfaces bridge {} member interface'.format(br))
            if intf['name'] in tmp:
                raise ConfigError('{} can be assigned to any one bridge only'.format(intf['name']))

    return None

def generate(bridge):
    if bridge is None:
        return None

    return None

def apply(bridge):
    if bridge is None:
        return None

    if bridge['deleted']:
        # bridges need to be shutdown first
        os.system("ip link set dev {} down".format(bridge['br_name']))
        # delete bridge
        os.system("brctl delbr {}".format(bridge['br_name']))
    else:
        # create bridge if it does not exist
        if not os.path.exists("/sys/class/net/" + bridge['br_name']):
            os.system("brctl addbr {}".format(bridge['br_name']))

        # assemble bridge configuration
        # configuration is passed via subprocess to brctl
        cmd = ''

        # set ageing time
        cmd += 'brctl setageing {} {}'.format(bridge['br_name'], bridge['aging'])
        cmd += ' && '

        # set bridge forward delay
        cmd += 'brctl setfd {} {}'.format(bridge['br_name'], bridge['forwarding_delay'])
        cmd += ' && '

        # set hello time
        cmd += 'brctl sethello {} {}'.format(bridge['br_name'], bridge['hello_time'])
        cmd += ' && '

        # set max message age
        cmd += 'brctl setmaxage {} {}'.format(bridge['br_name'], bridge['max_age'])
        cmd += ' && '

        # set bridge priority
        cmd += 'brctl setbridgeprio {} {}'.format(bridge['br_name'], bridge['priority'])
        cmd += ' && '

        # turn stp on/off
        cmd += 'brctl stp {} {}'.format(bridge['br_name'], bridge['stp'])

        for intf in bridge['member_remove']:
            # remove interface from bridge
            cmd += ' && '
            cmd += 'brctl delif {} {}'.format(bridge['br_name'], intf)

        for intf in bridge['member']:
            # add interface to bridge
            # but only if it is not yet member of this bridge
            if not os.path.exists('/sys/devices/virtual/net/' + bridge['br_name'] + '/brif/' + intf['name']):
                cmd += ' && '
                cmd += 'brctl addif {} {}'.format(bridge['br_name'], intf['name'])

            # set bridge port cost
            if intf['cost']:
                cmd += ' && '
                cmd += 'brctl setpathcost {} {} {}'.format(bridge['br_name'], intf['name'], intf['cost'])

            # set bridge port priority
            if intf['priority']:
                cmd += ' && '
                cmd += 'brctl setportprio {} {} {}'.format(bridge['br_name'], intf['name'], intf['priority'])

        subprocess_cmd(cmd)

        # Change interface MAC address
        if bridge['mac']:
            VyIfconfig.set_mac_address(bridge['br_name'], bridge['mac'])
        else:
            print("TODO: change mac mac address to the autoselected one based on member interfaces"

        # update interface description used e.g. within SNMP
        VyIfconfig.set_description(bridge['br_name'], bridge['description'])

        # Ignore link state changes?
        VyIfconfig.set_link_detect(bridge['br_name'], bridge['disable_link_detect'])

        # enable or disable IGMP querier
        VyIfconfig.set_multicast_querier(bridge['br_name'], bridge['igmp_querier'])

        # ARP cache entry timeout in seconds
        VyIfconfig.set_arp_cache_timeout(bridge['br_name'], bridge['arp_cache_timeout_ms'])

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
