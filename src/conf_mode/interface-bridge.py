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
    'priority': '32768',
    'stp': 'off'
}

def subprocess_cmd(command):
    process = subprocess.Popen(command,stdout=subprocess.PIPE, shell=True)
    proc_stdout = process.communicate()[0].strip()
    print(proc_stdout)

def get_config():
    bridge = copy.deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    try:
        bridge['br_name'] = os.environ['VYOS_TAGNODE_VALUE']
        print("Executing script for interface: " + bridge['br_name'])
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

    # Enable or disable IGMP querier
    if conf.exists('igmp-snooping querier'):
        tmp = conf.return_value('igmp-snooping querier')
        if tmp == "enable":
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

    # Priority for this bridge
    if conf.exists('priority'):
        bridge['priority'] = conf.return_value('priority')

    # Enable spanning tree protocol
    if conf.exists('stp'):
        tmp = conf.return_value('stp')
        if tmp == "true":
            bridge['stp'] = 'on'

    return bridge

def verify(bridge):
    if bridge is None:
        return None

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
        os.system("ip link set dev {0} down".format(bridge['br_name']))
        # delete bridge
        os.system("brctl delbr {0}".format(bridge['br_name']))
    else:
        # create bridge if it does not exist
        if not os.path.exists("/sys/class/net/" + bridge['br_name']):
            os.system("brctl addbr {0}".format(bridge['br_name']))

        # assemble bridge configuration
        # configuration is passed via subprocess to brctl
        cmd = ''

        # set ageing time
        cmd += 'brctl setageing {0} {1}'.format(bridge['br_name'], bridge['aging'])
        cmd += ' && '

        # set bridge forward delay
        cmd += 'brctl setfd {0} {1}'.format(bridge['br_name'], bridge['forwarding_delay'])
        cmd += ' && '

        # set hello time
        cmd += 'brctl sethello {0} {1}'.format(bridge['br_name'], bridge['hello_time'])
        cmd += ' && '

        # set max message age
        cmd += 'brctl setmaxage {0} {1}'.format(bridge['br_name'], bridge['max_age'])
        cmd += ' && '

        # set bridge priority
        cmd += 'brctl setbridgeprio {0} {1}'.format(bridge['br_name'], bridge['priority'])
        cmd += ' && '

        # turn stp on/off
        cmd += 'brctl stp {0} {1}'.format(bridge['br_name'], bridge['stp'])

        subprocess_cmd(cmd)

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
