#!/usr/bin/env python3
#
# Copyright (C) 2020-2022 VyOS maintainers and contributors
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
from json import loads

from vyos.config import Config
from vyos.configdict import node_changed
from vyos.ifconfig import Interface
from vyos.template import render
from vyos.util import call
from vyos.util import cmd
from vyos.util import dict_search
from vyos.util import get_interface_config
from vyos.util import popen
from vyos.util import run
from vyos.util import sysctl_write
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

config_file = '/etc/iproute2/rt_tables.d/vyos-vrf.conf'
nft_vrf_config = '/tmp/nftables-vrf-zones'

def has_rule(af : str, priority : int, table : str):
    """ Check if a given ip rule exists """
    if af not in ['-4', '-6']:
        raise ValueError()
    command = f'ip -j {af} rule show'
    for tmp in loads(cmd(command)):
        if {'priority', 'table'} <= set(tmp):
            if tmp['priority'] == priority and tmp['table'] == table:
                return True
    return False

def vrf_interfaces(c, match):
    matched = []
    old_level = c.get_level()
    c.set_level(['interfaces'])
    section = c.get_config_dict([], get_first_key=True)
    for type in section:
        interfaces = section[type]
        for name in interfaces:
            interface = interfaces[name]
            if 'vrf' in interface:
                v = interface.get('vrf', '')
                if v == match:
                    matched.append(name)

    c.set_level(old_level)
    return matched

def vrf_routing(c, match):
    matched = []
    old_level = c.get_level()
    c.set_level(['protocols', 'vrf'])
    if match in c.list_nodes([]):
        matched.append(match)

    c.set_level(old_level)
    return matched

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['vrf']
    vrf = conf.get_config_dict(base, key_mangling=('-', '_'),
                               no_tag_node_value_mangle=True, get_first_key=True)

    # determine which VRF has been removed
    for name in node_changed(conf, base + ['name']):
        if 'vrf_remove' not in vrf:
            vrf.update({'vrf_remove' : {}})

        vrf['vrf_remove'][name] = {}
        # get VRF bound interfaces
        interfaces = vrf_interfaces(conf, name)
        if interfaces: vrf['vrf_remove'][name]['interface'] = interfaces
        # get VRF bound routing instances
        routes = vrf_routing(conf, name)
        if routes: vrf['vrf_remove'][name]['route'] = routes

    return vrf

def verify(vrf):
    # ensure VRF is not assigned to any interface
    if 'vrf_remove' in vrf:
        for name, config in vrf['vrf_remove'].items():
            if 'interface' in config:
                raise ConfigError(f'Can not remove VRF "{name}", it still has '\
                                  f'member interfaces!')
            if 'route' in config:
                raise ConfigError(f'Can not remove VRF "{name}", it still has '\
                                  f'static routes installed!')

    if 'name' in vrf:
        table_ids = []
        for name, config in vrf['name'].items():
            # table id is mandatory
            if 'table' not in config:
                raise ConfigError(f'VRF "{name}" table id is mandatory!')

            # routing table id can't be changed - OS restriction
            if os.path.isdir(f'/sys/class/net/{name}'):
                tmp = str(dict_search('linkinfo.info_data.table', get_interface_config(name)))
                if tmp and tmp != config['table']:
                    raise ConfigError(f'VRF "{name}" table id modification not possible!')

            # VRf routing table ID must be unique on the system
            if config['table'] in table_ids:
                raise ConfigError(f'VRF "{name}" table id is not unique!')
            table_ids.append(config['table'])

    return None


def generate(vrf):
    render(config_file, 'vrf/vrf.conf.j2', vrf)
    # Render nftables zones config

    render(nft_vrf_config, 'firewall/nftables-vrf-zones.j2', vrf)

    return None


def apply(vrf):
    # Documentation
    #
    # - https://github.com/torvalds/linux/blob/master/Documentation/networking/vrf.txt
    # - https://github.com/Mellanox/mlxsw/wiki/Virtual-Routing-and-Forwarding-(VRF)
    # - https://github.com/Mellanox/mlxsw/wiki/L3-Tunneling
    # - https://netdevconf.info/1.1/proceedings/slides/ahern-vrf-tutorial.pdf
    # - https://netdevconf.info/1.2/slides/oct6/02_ahern_what_is_l3mdev_slides.pdf

    # set the default VRF global behaviour
    bind_all = '0'
    if 'bind_to_all' in vrf:
        bind_all = '1'
    sysctl_write('net.ipv4.tcp_l3mdev_accept', bind_all)
    sysctl_write('net.ipv4.udp_l3mdev_accept', bind_all)

    for tmp in (dict_search('vrf_remove', vrf) or []):
        if os.path.isdir(f'/sys/class/net/{tmp}'):
            call(f'ip link delete dev {tmp}')
            # Remove nftables conntrack zone map item
            nft_del_element = f'delete element inet vrf_zones ct_iface_map {{ "{tmp}" }}'
            cmd(f'nft {nft_del_element}')

    if 'name' in vrf:
        # Separate VRFs in conntrack table
        # check if table already exists
        _, err = popen('nft list table inet vrf_zones')
        # If not, create a table
        if err and os.path.exists(nft_vrf_config):
            cmd(f'nft -f {nft_vrf_config}')
            os.unlink(nft_vrf_config)

        # Linux routing uses rules to find tables - routing targets are then
        # looked up in those tables. If the lookup got a matching route, the
        # process ends.
        #
        # TL;DR; first table with a matching entry wins!
        #
        # You can see your routing table lookup rules using "ip rule", sadly the
        # local lookup is hit before any VRF lookup. Pinging an addresses from the
        # VRF will usually find a hit in the local table, and never reach the VRF
        # routing table - this is usually not what you want. Thus we will
        # re-arrange the tables and move the local lookup further down once VRFs
        # are enabled.
        #
        # Thanks to https://stbuehler.de/blog/article/2020/02/29/using_vrf__virtual_routing_and_forwarding__on_linux.html

        for afi in ['-4', '-6']:
            # move lookup local to pref 32765 (from 0)
            if not has_rule(afi, 32765, 'local'):
                call(f'ip {afi} rule add pref 32765 table local')
            if has_rule(afi, 0, 'local'):
                call(f'ip {afi} rule del pref 0')
            # make sure that in VRFs after failed lookup in the VRF specific table
            # nothing else is reached
            if not has_rule(afi, 1000, 'l3mdev'):
                # this should be added by the kernel when a VRF is created
                # add it here for completeness
                call(f'ip {afi} rule add pref 1000 l3mdev protocol kernel')

            # add another rule with an unreachable target which only triggers in VRF context
            # if a route could not be reached
            if not has_rule(afi, 2000, 'l3mdev'):
                call(f'ip {afi} rule add pref 2000 l3mdev unreachable')

        for name, config in vrf['name'].items():
            table = config['table']
            if not os.path.isdir(f'/sys/class/net/{name}'):
                # For each VRF apart from your default context create a VRF
                # interface with a separate routing table
                call(f'ip link add {name} type vrf table {table}')

            # set VRF description for e.g. SNMP monitoring
            vrf_if = Interface(name)
            # We also should add proper loopback IP addresses to the newly added
            # VRF for services bound to the loopback address (SNMP, NTP)
            vrf_if.add_addr('127.0.0.1/8')
            vrf_if.add_addr('::1/128')
            # add VRF description if available
            vrf_if.set_alias(config.get('description', ''))

            # Enable/Disable IPv4 forwarding
            tmp = dict_search('ip.disable_forwarding', config)
            value = '0' if (tmp != None) else '1'
            vrf_if.set_ipv4_forwarding(value)
            # Enable/Disable IPv6 forwarding
            tmp = dict_search('ipv6.disable_forwarding', config)
            value = '0' if (tmp != None) else '1'
            vrf_if.set_ipv6_forwarding(value)

            # Enable/Disable of an interface must always be done at the end of the
            # derived class to make use of the ref-counting set_admin_state()
            # function. We will only enable the interface if 'up' was called as
            # often as 'down'. This is required by some interface implementations
            # as certain parameters can only be changed when the interface is
            # in admin-down state. This ensures the link does not flap during
            # reconfiguration.
            state = 'down' if 'disable' in config else 'up'
            vrf_if.set_admin_state(state)
            # Add nftables conntrack zone map item
            nft_add_element = f'add element inet vrf_zones ct_iface_map {{ "{name}" : {table} }}'
            cmd(f'nft {nft_add_element}')


    # return to default lookup preference when no VRF is configured
    if 'name' not in vrf:
        # Remove VRF zones table from nftables
        tmp = run('nft list table inet vrf_zones')
        if tmp == 0:
            cmd('nft delete table inet vrf_zones')

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
