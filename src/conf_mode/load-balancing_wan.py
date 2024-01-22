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
from vyos.configdep import set_dependents, call_dependents
from vyos.utils.process import cmd
from vyos.template import render
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
    lb = conf.get_config_dict(base, key_mangling=('-', '_'),
                              no_tag_node_value_mangle=True,
                              get_first_key=True,
                              with_recursive_defaults=True)

    # prune limit key if not set by user
    for rule in lb.get('rule', []):
        if lb.from_defaults(['rule', rule, 'limit']):
            del lb['rule'][rule]['limit']

    set_dependents('conntrack', conf)

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

    call_dependents()

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
