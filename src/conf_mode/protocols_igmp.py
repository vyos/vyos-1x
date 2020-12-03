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

from vyos import ConfigError
from vyos.config import Config
from vyos.util import call, process_named_running
from vyos.template import render
from signal import SIGTERM

from vyos import airbag
airbag.enable()

# Required to use the full path to pimd, in another case daemon will not be started
pimd_cmd = f'/usr/lib/frr/pimd -d -F traditional --daemon -A 127.0.0.1'

config_file = r'/tmp/igmp.frr'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    igmp_conf = {
        'igmp_conf' : False,
        'pim_conf'  : False,
        'igmp_proxy_conf' : False,
        'old_ifaces'    : {},
        'ifaces'    : {}
    }
    if not (conf.exists('protocols igmp') or conf.exists_effective('protocols igmp')):
        return None

    if conf.exists('protocols igmp-proxy'):
        igmp_conf['igmp_proxy_conf'] = True

    if conf.exists('protocols pim'):
        igmp_conf['pim_conf'] = True

    if conf.exists('protocols igmp'):
        igmp_conf['igmp_conf'] = True

    conf.set_level('protocols igmp')

    # # Get interfaces
    for iface in conf.list_effective_nodes('interface'):
        igmp_conf['old_ifaces'].update({
            iface : {
                'version' : conf.return_effective_value('interface {0} version'.format(iface)),
                'query_interval' : conf.return_effective_value('interface {0} query-interval'.format(iface)),
                'query_max_resp_time' : conf.return_effective_value('interface {0} query-max-response-time'.format(iface)),
                'gr_join' : {}
            }
        })
        for gr_join in conf.list_effective_nodes('interface {0} join'.format(iface)):
            igmp_conf['old_ifaces'][iface]['gr_join'][gr_join] = conf.return_effective_values('interface {0} join {1} source'.format(iface, gr_join))

    for iface in conf.list_nodes('interface'):
        igmp_conf['ifaces'].update({
            iface : {
                'version' : conf.return_value('interface {0} version'.format(iface)),
                'query_interval' : conf.return_value('interface {0} query-interval'.format(iface)),
                'query_max_resp_time' : conf.return_value('interface {0} query-max-response-time'.format(iface)),
                'gr_join' : {}
            }
        })
        for gr_join in conf.list_nodes('interface {0} join'.format(iface)):
            igmp_conf['ifaces'][iface]['gr_join'][gr_join] = conf.return_values('interface {0} join {1} source'.format(iface, gr_join))

    return igmp_conf

def verify(igmp):
    if igmp is None:
        return None

    if igmp['igmp_conf']:
        # Check conflict with IGMP-Proxy
        if igmp['igmp_proxy_conf']:
            raise ConfigError(f"IGMP proxy and PIM cannot be both configured at the same time")

        # Check interfaces
        if not igmp['ifaces']:
            raise ConfigError(f"IGMP require defined interfaces!")
        # Check, is this multicast group
        for intfc in igmp['ifaces']:
            for gr_addr in igmp['ifaces'][intfc]['gr_join']:
                if IPv4Address(gr_addr) < IPv4Address('224.0.0.0'):
                    raise ConfigError(gr_addr + " not a multicast group")

def generate(igmp):
    if igmp is None:
        return None

    render(config_file, 'frr/igmp.frr.tmpl', igmp)
    return None

def apply(igmp):
    if igmp is None:
        return None

    pim_pid = process_named_running('pimd')
    if igmp['igmp_conf'] or igmp['pim_conf']:
        if not pim_pid:
            call(pimd_cmd)

        if os.path.exists(config_file):
            call(f'vtysh -d pimd -f {config_file}')
            os.remove(config_file)
    elif pim_pid:
        os.kill(int(pim_pid), SIGTERM)

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
