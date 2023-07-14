#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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
from shutil import rmtree

from vyos.base import Warning
from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.utils.process import cmd
from vyos.template import render
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

load_balancing_dir = '/run/load-balance'
load_balancing_conf_file = f'{load_balancing_dir}/wlb.conf'
systemd_service = 'vyos-wan-load-balance.service'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['load-balancing', 'wan']
    lb = conf.get_config_dict(base,
                              get_first_key=True,
                              key_mangling=('-', '_'),
                              no_tag_node_value_mangle=True)

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)
    # lb base default values can not be merged here - remove and add them later
    if 'interface_health' in default_values:
        del default_values['interface_health']
    if 'rule' in default_values:
        del default_values['rule']
    lb = dict_merge(default_values, lb)

    if 'interface_health' in lb:
        for iface in lb.get('interface_health'):
            default_values_iface = defaults(base + ['interface-health'])
            if 'test' in default_values_iface:
                del default_values_iface['test']
            lb['interface_health'][iface] = dict_merge(
                default_values_iface, lb['interface_health'][iface])
            if 'test' in lb['interface_health'][iface]:
                for node_test in lb['interface_health'][iface]['test']:
                    default_values_test = defaults(base +
                                                   ['interface-health', 'test'])
                    lb['interface_health'][iface]['test'][node_test] = dict_merge(
                            default_values_test,
                            lb['interface_health'][iface]['test'][node_test])

    if 'rule' in lb:
        for rule in lb.get('rule'):
            default_values_rule = defaults(base + ['rule'])
            if 'interface' in default_values_rule:
                del default_values_rule['interface']
            lb['rule'][rule] = dict_merge(default_values_rule, lb['rule'][rule])
            if not conf.exists(base + ['rule', rule, 'limit']):
                del lb['rule'][rule]['limit']
            if 'interface' in lb['rule'][rule]:
                for iface in lb['rule'][rule]['interface']:
                    default_values_rule_iface = defaults(base + ['rule', 'interface'])
                    lb['rule'][rule]['interface'][iface] = dict_merge(default_values_rule_iface, lb['rule'][rule]['interface'][iface])

    return lb


def verify(lb):
    if not lb:
        return None

    if 'interface_health' not in lb:
        raise ConfigError(
            'A valid WAN load-balance configuration requires an interface with a nexthop!'
        )

    for interface, interface_config in lb['interface_health'].items():
        if 'nexthop' not in interface_config:
            raise ConfigError(
                f'interface-health {interface} nexthop must be specified!')

        if 'test' in interface_config:
            for test_rule, test_config in interface_config['test'].items():
                if 'type' in test_config:
                    if test_config['type'] == 'user-defined' and 'test_script' not in test_config:
                        raise ConfigError(
                            f'test {test_rule} script must be defined for test-script!'
                        )

    if 'rule' not in lb:
        Warning(
            'At least one rule with an (outbound) interface must be defined for WAN load balancing to be active!'
        )
    else:
        for rule, rule_config in lb['rule'].items():
            if 'inbound_interface' not in rule_config:
                raise ConfigError(f'rule {rule} inbound-interface must be specified!')
            if {'failover', 'exclude'} <= set(rule_config):
                raise ConfigError(f'rule {rule} failover cannot be configured with exclude!')
            if {'limit', 'exclude'} <= set(rule_config):
                raise ConfigError(f'rule {rule} limit cannot be used with exclude!')
            if 'interface' not in rule_config:
                if 'exclude' not in rule_config:
                    Warning(
                        f'rule {rule} will be inactive because no (outbound) interfaces have been defined for this rule'
                    )
            for direction in {'source', 'destination'}:
                if direction in rule_config:
                    if 'protocol' in rule_config and 'port' in rule_config[
                            direction]:
                        if rule_config['protocol'] not in {'tcp', 'udp'}:
                            raise ConfigError('ports can only be specified when protocol is "tcp" or "udp"')


def generate(lb):
    if not lb:
        # Delete /run/load-balance/wlb.conf
        if os.path.isfile(load_balancing_conf_file):
            os.unlink(load_balancing_conf_file)
        # Delete old directories
        if os.path.isdir(load_balancing_dir):
            rmtree(load_balancing_dir, ignore_errors=True)
        if os.path.exists('/var/run/load-balance/wlb.out'):
            os.unlink('/var/run/load-balance/wlb.out')

        return None

    # Create load-balance dir
    if not os.path.isdir(load_balancing_dir):
        os.mkdir(load_balancing_dir)

    render(load_balancing_conf_file, 'load-balancing/wlb.conf.j2', lb)

    return None


def apply(lb):
    if not lb:
        try:
            cmd(f'systemctl stop {systemd_service}')
        except Exception as e:
            print(f"Error message: {e}")

    else:
        cmd('sudo sysctl -w net.netfilter.nf_conntrack_acct=1')
        cmd(f'systemctl restart {systemd_service}')

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
