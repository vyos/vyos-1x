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

import jmespath
import json
import os

from sys import exit
from netifaces import interfaces

from vyos.base import Warning
from vyos.config import Config
from vyos.configdep import set_dependents, call_dependents
from vyos.template import render
from vyos.utils.process import cmd
from vyos.utils.kernel import check_kmod
from vyos.utils.dict import dict_search
from vyos.template import is_ipv6
from vyos import ConfigError
from vyos import airbag
airbag.enable()

k_mod = ['nft_nat', 'nft_chain_nat']

nftables_nat66_config = '/run/nftables_nat66.nft'
ndppd_config = '/run/ndppd/ndppd.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['nat66']
    nat = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    set_dependents('conntrack', conf)

    if not conf.exists(base):
        nat['deleted'] = ''

    return nat

def verify(nat):
    if not nat or 'deleted' in nat:
        # no need to verify the CLI as NAT66 is going to be deactivated
        return None

    if dict_search('source.rule', nat):
        for rule, config in dict_search('source.rule', nat).items():
            err_msg = f'Source NAT66 configuration error in rule {rule}:'

            if 'outbound_interface' in config:
                if 'name' in config['outbound_interface'] and 'group' in config['outbound_interface']:
                    raise ConfigError(f'{err_msg} - Cannot specify both interface group and interface name for nat source rule "{rule}"')
                elif 'name' in config['outbound_interface']:
                    if config['outbound_interface']['name'] not in 'any' and config['outbound_interface']['name'] not in interfaces():
                        Warning(f'{err_msg} - interface "{config["outbound_interface"]["name"]}" does not exist on this system')

            addr = dict_search('translation.address', config)
            if addr != None:
                if addr != 'masquerade' and not is_ipv6(addr):
                    raise ConfigError(f'IPv6 address {addr} is not a valid address')
            else:
                if 'exclude' not in config:
                    raise ConfigError(f'{err_msg} translation address not specified')

            prefix = dict_search('source.prefix', config)
            if prefix != None:
                if not is_ipv6(prefix):
                    raise ConfigError(f'{err_msg} source-prefix not specified')

    if dict_search('destination.rule', nat):
        for rule, config in dict_search('destination.rule', nat).items():
            err_msg = f'Destination NAT66 configuration error in rule {rule}:'

            if 'inbound_interface' in config:
                if 'name' in config['inbound_interface'] and 'group' in config['inbound_interface']:
                    raise ConfigError(f'{err_msg} - Cannot specify both interface group and interface name for destination nat rule "{rule}"')
                elif 'name' in config['inbound_interface']:
                    if config['inbound_interface']['name'] not in 'any' and config['inbound_interface']['name'] not in interfaces():
                        Warning(f'{err_msg} -  interface "{config["inbound_interface"]["name"]}" does not exist on this system')

    return None

def generate(nat):
    if not os.path.exists(nftables_nat66_config):
        nat['first_install'] = True

    render(nftables_nat66_config, 'firewall/nftables-nat66.j2', nat, permission=0o755)
    render(ndppd_config, 'ndppd/ndppd.conf.j2', nat, permission=0o755)
    return None

def apply(nat):
    if not nat:
        return None

    cmd(f'nft -f {nftables_nat66_config}')

    if 'deleted' in nat or not dict_search('source.rule', nat):
        cmd('systemctl stop ndppd')
        if os.path.isfile(ndppd_config):
            os.unlink(ndppd_config)
    else:
        cmd('systemctl restart ndppd')

    call_dependents()

    return None

if __name__ == '__main__':
    try:
        check_kmod(k_mod)
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
