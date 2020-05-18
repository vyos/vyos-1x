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

from ipaddress import IPv4Address
from sys import exit

from vyos.config import Config
from vyos import ConfigError
from vyos.command import call
from vyos.template import render


config_file = r'/tmp/pimd.frr'

def get_config():
    conf = Config()
    pim_conf = {
        'pim_conf' : False,
        'old_pim' : {
            'ifaces' : {},
            'rp'     : {}
        },
        'pim' : {
            'ifaces' : {},
            'rp'     : {}
        }
    }
    if not (conf.exists('protocols pim') or conf.exists_effective('protocols pim')):
        return None

    if conf.exists('protocols pim'):
        pim_conf['pim_conf'] = True

    conf.set_level('protocols pim')

    # Get interfaces
    for iface in conf.list_effective_nodes('interface'):
        pim_conf['old_pim']['ifaces'].update({
            iface : {
                'hello' : conf.return_effective_value('interface {0} hello'.format(iface)),
                'dr_prio' : conf.return_effective_value('interface {0} dr-priority'.format(iface))
            }
        })

    for iface in conf.list_nodes('interface'):
        pim_conf['pim']['ifaces'].update({
            iface : {
                'hello' : conf.return_value('interface {0} hello'.format(iface)),
                'dr_prio' : conf.return_value('interface {0} dr-priority'.format(iface)),
            }
        })

    conf.set_level('protocols pim rp')

    # Get RPs addresses
    for rp_addr in conf.list_effective_nodes('address'):
        pim_conf['old_pim']['rp'][rp_addr] = conf.return_effective_values('address {0} group'.format(rp_addr))

    for rp_addr in conf.list_nodes('address'):
        pim_conf['pim']['rp'][rp_addr] = conf.return_values('address {0} group'.format(rp_addr))

    # Get RP keep-alive-timer
    if conf.exists_effective('rp keep-alive-timer'):
        pim_conf['old_pim']['rp_keep_alive'] = conf.return_effective_value('rp keep-alive-timer')
    if conf.exists('rp keep-alive-timer'):
        pim_conf['pim']['rp_keep_alive'] = conf.return_value('rp keep-alive-timer')

    return pim_conf

def verify(pim):
    if pim is None:
        return None

    if pim['pim_conf']:
        # Check interfaces
        if not pim['pim']['ifaces']:
            raise ConfigError(f"PIM require defined interfaces!")

        if not pim['pim']['rp']:
            raise ConfigError(f"RP address required")

        # Check unique multicast groups
        uniq_groups = []
        for rp_addr in pim['pim']['rp']:
            if not pim['pim']['rp'][rp_addr]:
                raise ConfigError(f"Group should be specified for RP " + rp_addr)
            for group in pim['pim']['rp'][rp_addr]:
                if (group in uniq_groups):
                    raise ConfigError(f"Group range " + group + " specified cannot exact match another")

                # Check, is this multicast group
                gr_addr = group.split('/')
                if IPv4Address(gr_addr[0]) < IPv4Address('224.0.0.0'):
                    raise ConfigError(group + " not a multicast group")

            uniq_groups.extend(pim['pim']['rp'][rp_addr])

def generate(pim):
    if pim is None:
        return None

    render(config_file, 'frr/pimd.frr.tmpl', pim)
    return None

def apply(pim):
    if pim is None:
        return None

    if os.path.exists(config_file):
        call("vtysh -d pimd -f " + config_file)
        os.remove(config_file)

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
