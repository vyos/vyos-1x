#!/usr/bin/env python3
#
# Copyright (C) 2020-2021 VyOS maintainers and contributors
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
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = r'/etc/iproute2/rt_tables.d/vyos-vrf.conf'

def list_rules():
    command = 'ip -j -4 rule show'
    answer = loads(cmd(command))
    return [_ for _ in answer if _]

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
    vrf = conf.get_config_dict(base, get_first_key=True)

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
                tmp = loads(cmd(f'ip -j -d link show {name}'))[0]
                tmp = str(dict_search('linkinfo.info_data.table', tmp))
                if tmp and tmp != config['table']:
                    raise ConfigError(f'VRF "{name}" table id modification not possible!')

            # VRf routing table ID must be unique on the system
            if config['table'] in table_ids:
                raise ConfigError(f'VRF "{name}" table id is not unique!')
            table_ids.append(config['table'])

    return None

def generate(vrf):
    render(config_file, 'vrf/vrf.conf.tmpl', vrf)
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
    if 'bind-to-all' in vrf:
        bind_all = '1'
    call(f'sysctl -wq net.ipv4.tcp_l3mdev_accept={bind_all}')
    call(f'sysctl -wq net.ipv4.udp_l3mdev_accept={bind_all}')

    for tmp in (dict_search('vrf_remove', vrf) or []):
        if os.path.isdir(f'/sys/class/net/{tmp}'):
            call(f'ip -4 route del vrf {tmp} unreachable default metric 4278198272')
            call(f'ip -6 route del vrf {tmp} unreachable default metric 4278198272')
            call(f'ip link delete dev {tmp}')

    if 'name' in vrf:
        for name, config in vrf['name'].items():
            table = config['table']

            if not os.path.isdir(f'/sys/class/net/{name}'):
                # For each VRF apart from your default context create a VRF
                # interface with a separate routing table
                call(f'ip link add {name} type vrf table {table}')
                # The kernel Documentation/networking/vrf.txt also recommends
                # adding unreachable routes to the VRF routing tables so that routes
                # afterwards are taken.
                call(f'ip -4 route add vrf {name} unreachable default metric 4278198272')
                call(f'ip -6 route add vrf {name} unreachable default metric 4278198272')
                # We also should add proper loopback IP addresses to the newly
                # created VRFs for services bound to the loopback address (SNMP, NTP)
                call(f'ip -4 addr add 127.0.0.1/8 dev {name}')
                call(f'ip -6 addr add ::1/128 dev {name}')

            # set VRF description for e.g. SNMP monitoring
            vrf_if = Interface(name)
            vrf_if.set_alias(config.get('description', ''))
            # Enable/Disable of an interface must always be done at the end of the
            # derived class to make use of the ref-counting set_admin_state()
            # function. We will only enable the interface if 'up' was called as
            # often as 'down'. This is required by some interface implementations
            # as certain parameters can only be changed when the interface is
            # in admin-down state. This ensures the link does not flap during
            # reconfiguration.
            state = 'down' if 'disable' in config else 'up'
            vrf_if.set_admin_state(state)

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
    # re-arrange the tables and move the local lookup furhter down once VRFs
    # are enabled.

    # get current preference on local table
    local_pref = [r.get('priority') for r in list_rules() if r.get('table') == 'local'][0]

    # change preference when VRFs are enabled and local lookup table is default
    if not local_pref and 'name' in vrf:
        for af in ['-4', '-6']:
            call(f'ip {af} rule add pref 32765 table local')
            call(f'ip {af} rule del pref 0')

    # return to default lookup preference when no VRF is configured
    if 'name' not in vrf:
        for af in ['-4', '-6']:
            call(f'ip {af} rule add pref 0 table local')
            call(f'ip {af} rule del pref 32765')

            # clean out l3mdev-table rule if present
            if 1000 in [r.get('priority') for r in list_rules() if r.get('priority') == 1000]:
                call(f'ip {af} rule del pref 1000')

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
