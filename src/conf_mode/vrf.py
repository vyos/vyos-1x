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
from copy import deepcopy
from json import loads

from vyos.config import Config
from vyos.configdict import list_diff
from vyos.ifconfig import Interface
from vyos.util import read_file, cmd
from vyos import ConfigError
from vyos.template import render

from vyos import airbag
airbag.enable()

config_file = r'/etc/iproute2/rt_tables.d/vyos-vrf.conf'

default_config_data = {
    'bind_to_all': '0',
    'deleted': False,
    'vrf_add': [],
    'vrf_existing': [],
    'vrf_remove': []
}

def _cmd(command):
    cmd(command, raising=ConfigError, message='Error changing VRF')

def list_rules():
    command = 'ip -j -4 rule show'
    answer = loads(cmd(command))
    return [_ for _ in answer if _]

def vrf_interfaces(c, match):
    matched = []
    old_level = c.get_level()
    c.set_level(['interfaces'])
    section = c.get_config_dict([])
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


def get_config():
    conf = Config()
    vrf_config = deepcopy(default_config_data)

    cfg_base = ['vrf']
    if not conf.exists(cfg_base):
        # get all currently effetive VRFs and mark them for deletion
        vrf_config['vrf_remove'] = conf.list_effective_nodes(cfg_base + ['name'])
    else:
        # set configuration level base
        conf.set_level(cfg_base)

        # Should services be allowed to bind to all VRFs?
        if conf.exists(['bind-to-all']):
            vrf_config['bind_to_all'] = '1'

        # Determine vrf interfaces (currently effective) - to determine which
        # vrf interface is no longer present and needs to be removed
        eff_vrf = conf.list_effective_nodes(['name'])
        act_vrf = conf.list_nodes(['name'])
        vrf_config['vrf_remove'] = list_diff(eff_vrf, act_vrf)

        # read in individual VRF definition and build up
        # configuration
        for name in conf.list_nodes(['name']):
            vrf_inst = {
                'description' : '',
                'members': [],
                'name' : name,
                'table' : '',
                'table_mod': False
            }
            conf.set_level(cfg_base + ['name', name])

            if conf.exists(['table']):
                # VRF table can't be changed on demand, thus we need to read in the
                # current and the effective routing table number
                act_table = conf.return_value(['table'])
                eff_table = conf.return_effective_value(['table'])
                vrf_inst['table'] = act_table
                if eff_table and eff_table != act_table:
                    vrf_inst['table_mod'] = True

            if conf.exists(['description']):
                vrf_inst['description'] = conf.return_value(['description'])

            # append individual VRF configuration to global configuration list
            vrf_config['vrf_add'].append(vrf_inst)

    # set configuration level base
    conf.set_level(cfg_base)

    # check VRFs which need to be removed as they are not allowed to have
    # interfaces attached
    tmp = []
    for name in vrf_config['vrf_remove']:
        vrf_inst = {
            'interfaces': [],
            'name': name,
            'routes': []
        }

        # find member interfaces of this particulat VRF
        vrf_inst['interfaces'] = vrf_interfaces(conf, name)

        # find routing protocols used by this VRF
        vrf_inst['routes'] = vrf_routing(conf, name)

        # append individual VRF configuration to temporary configuration list
        tmp.append(vrf_inst)

    # replace values in vrf_remove with list of dictionaries
    # as we need it in verify() - we can't delete a VRF with members attached
    vrf_config['vrf_remove'] = tmp
    return vrf_config

def verify(vrf_config):
    # ensure VRF is not assigned to any interface
    for vrf in vrf_config['vrf_remove']:
        if len(vrf['interfaces']) > 0:
            raise ConfigError(f"VRF {vrf['name']} can not be deleted. It has active member interfaces!")

        if len(vrf['routes']) > 0:
            raise ConfigError(f"VRF {vrf['name']} can not be deleted. It has active routing protocols!")

    table_ids = []
    for vrf in vrf_config['vrf_add']:
        # table id is mandatory
        if not vrf['table']:
            raise ConfigError(f"VRF {vrf['name']} table id is mandatory!")

        # routing table id can't be changed - OS restriction
        if vrf['table_mod']:
            raise ConfigError(f"VRF {vrf['name']} table id modification is not possible!")

        # VRf routing table ID must be unique on the system
        if vrf['table'] in table_ids:
            raise ConfigError(f"VRF {vrf['name']} table id {vrf['table']} is not unique!")

        table_ids.append(vrf['table'])

    return None

def generate(vrf_config):
    render(config_file, 'vrf/vrf.conf.tmpl', vrf_config)
    return None

def apply(vrf_config):
    # Documentation
    #
    # - https://github.com/torvalds/linux/blob/master/Documentation/networking/vrf.txt
    # - https://github.com/Mellanox/mlxsw/wiki/Virtual-Routing-and-Forwarding-(VRF)
    # - https://github.com/Mellanox/mlxsw/wiki/L3-Tunneling
    # - https://netdevconf.info/1.1/proceedings/slides/ahern-vrf-tutorial.pdf
    # - https://netdevconf.info/1.2/slides/oct6/02_ahern_what_is_l3mdev_slides.pdf

    # set the default VRF global behaviour
    bind_all = vrf_config['bind_to_all']
    if read_file('/proc/sys/net/ipv4/tcp_l3mdev_accept') != bind_all:
        _cmd(f'sysctl -wq net.ipv4.tcp_l3mdev_accept={bind_all}')
        _cmd(f'sysctl -wq net.ipv4.udp_l3mdev_accept={bind_all}')

    for vrf in vrf_config['vrf_remove']:
        name = vrf['name']
        if os.path.isdir(f'/sys/class/net/{name}'):
            _cmd(f'sudo ip -4 route del vrf {name} unreachable default metric 4278198272')
            _cmd(f'sudo ip -6 route del vrf {name} unreachable default metric 4278198272')
            _cmd(f'ip link delete dev {name}')

    for vrf in vrf_config['vrf_add']:
        name = vrf['name']
        table = vrf['table']

        if not os.path.isdir(f'/sys/class/net/{name}'):
            # For each VRF apart from your default context create a VRF
            # interface with a separate routing table
            _cmd(f'ip link add {name} type vrf table {table}')
            # Start VRf
            _cmd(f'ip link set dev {name} up')
            # The kernel Documentation/networking/vrf.txt also recommends
            # adding unreachable routes to the VRF routing tables so that routes
            # afterwards are taken.
            _cmd(f'ip -4 route add vrf {name} unreachable default metric 4278198272')
            _cmd(f'ip -6 route add vrf {name} unreachable default metric 4278198272')

        # set VRF description for e.g. SNMP monitoring
        Interface(name).set_alias(vrf['description'])

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
    if not local_pref and vrf_config['vrf_add']:
        for af in ['-4', '-6']:
            _cmd(f'ip {af} rule add pref 32765 table local')
            _cmd(f'ip {af} rule del pref 0')

    # return to default lookup preference when no VRF is configured
    if not vrf_config['vrf_add']:
        for af in ['-4', '-6']:
            _cmd(f'ip {af} rule add pref 0 table local')
            _cmd(f'ip {af} rule del pref 32765')

            # clean out l3mdev-table rule if present
            if 1000 in [r.get('priority') for r in list_rules() if r.get('priority') == 1000]:
                _cmd(f'ip {af} rule del pref 1000')

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
