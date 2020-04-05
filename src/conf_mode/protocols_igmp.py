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
#

import sys
import jinja2
import copy
import os
import vyos.validate

from vyos import ConfigError
from vyos.config import Config
from ipaddress import IPv4Address

config_file = r'/tmp/igmp.frr'

# Please be careful if you edit the template.
config_tmpl = """
!
{% for iface in old_ifaces -%}
interface {{ iface }}
{% for group in old_ifaces[iface].gr_join -%}
{% if old_ifaces[iface].gr_join[group] -%}
{% for source in old_ifaces[iface].gr_join[group] -%}
no ip igmp join {{ group }} {{ source }}
{% endfor -%}
{% else -%}
no ip igmp join {{ group }}
{% endif -%}
{% endfor -%}
no ip igmp
!
{% endfor -%}
{% for iface in ifaces -%}
interface {{ iface }}
{% if ifaces[iface].version -%}
ip igmp version {{ ifaces[iface].version }}
{% else -%}
{# IGMP default version 3 #}
ip igmp
{% endif -%}
{% if ifaces[iface].query_interval -%}
ip igmp query-interval {{ ifaces[iface].query_interval }}
{% endif -%}
{% if ifaces[iface].query_max_resp_time -%}
ip igmp query-max-response-time {{ ifaces[iface].query_max_resp_time }}
{% endif -%}
{% for group in ifaces[iface].gr_join -%}
{% if ifaces[iface].gr_join[group] -%}
{% for source in ifaces[iface].gr_join[group] -%}
ip igmp join {{ group }} {{ source }}
{% endfor -%}
{% else -%}
ip igmp join {{ group }}
{% endif -%}
{% endfor -%}
!
{% endfor -%}
!
"""

def get_config():
    conf = Config()
    igmp_conf = {
        'igmp_conf' : False,
        'old_ifaces'    : {},
        'ifaces'    : {}
    }
    if not (conf.exists('protocols igmp') or conf.exists_effective('protocols igmp')):
        return None

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

    tmpl = jinja2.Template(config_tmpl)
    config_text = tmpl.render(igmp)
    with open(config_file, 'w') as f:
        f.write(config_text)

    return None

def apply(igmp):
    if igmp is None:
        return None

    if os.path.exists(config_file):
        os.system("sudo vtysh -d pimd -f " + config_file)
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
        sys.exit(1)
