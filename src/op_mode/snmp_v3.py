#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# File: snmp_v3.py
# Purpose:
#    Show SNMP v3 information
#    Used by the "run show snmp v3" commands.

import sys
import jinja2
import argparse

from vyos.config import Config

parser = argparse.ArgumentParser(description='Retrieve SNMP v3 information')
parser.add_argument('--all',   action="store_true", help='Show all available information')
parser.add_argument('--group', action="store_true", help='Show the list of configured groups')
parser.add_argument('--trap',  action="store_true", help='Show the list of configured targets')
parser.add_argument('--user',  action="store_true", help='Show the list of configured users')
parser.add_argument('--view',  action="store_true", help='Show the list of configured views')

GROUP_OUTP_TMPL_SRC = """
SNMPv3 Groups:

    Group               View
    -----               ----
    {% if group %}{% for g in group %}
    {{ "%-20s" | format(g.name) }}{{ g.view }}({{ g.mode }})
    {% endfor %}{% endif %}
"""

TRAPTGT_OUTP_TMPL_SRC = """
SNMPv3 Trap-targets:

    Tpap-target                   Port   Protocol Auth Priv Type   EngineID                         User
    -----------                   ----   -------- ---- ---- ----   --------                         ----
    {% if trap %}{% for t in trap %}
    {{ "%-20s" | format(t.name) }}          {{ t.port }}    {{ t.proto }}      {{ t.auth }}  {{ t.priv }}  {{ t.type }}   {{ "%-32s" | format(t.engID) }} {{ t.user }}
    {% endfor %}{% endif %}
"""

USER_OUTP_TMPL_SRC = """
SNMPv3 Users:

    User                Auth Priv Mode Group
    ----                ---- ---- ---- -----
    {% if user %}{% for u in user %}
    {{ "%-20s" | format(u.name) }}{{ u.auth }}  {{ u.priv }}  {{ u.mode }}   {{ u.group }}
    {% endfor %}{% endif %}
"""

VIEW_OUTP_TMPL_SRC = """
SNMPv3 Views:
    {% if view %}{% for v in view %}
    View : {{ v.name }}
    OIDs : .{{ v.oids | join("\n           .")}}
    {% endfor %}{% endif %}
"""

if __name__ == '__main__':
    args = parser.parse_args()

    # Do nothing if service is not configured
    c = Config()
    if not c.exists_effective('service snmp v3'):
        print("SNMP v3 is not configured")
        sys.exit(0)

    data = {
        'group': [],
        'trap': [],
        'user': [],
        'view': []
    }

    if c.exists_effective('service snmp v3 group'):
        for g in c.list_effective_nodes('service snmp v3 group'):
            group = {
                'name': g,
                'mode': '',
                'view': ''
            }
            group['mode'] = c.return_effective_value('service snmp v3 group {0} mode'.format(g))
            group['view'] = c.return_effective_value('service snmp v3 group {0} view'.format(g))

            data['group'].append(group)

    if c.exists_effective('service snmp v3 user'):
        for u in c.list_effective_nodes('service snmp v3 user'):
            user = {
                'name' : u,
                'mode' : '',
                'auth' : '',
                'priv' : '',
                'group': ''
            }
            user['mode'] = c.return_effective_value('service snmp v3 user {0} mode'.format(u))
            user['auth'] = c.return_effective_value('service snmp v3 user {0} auth type'.format(u))
            user['priv'] = c.return_effective_value('service snmp v3 user {0} privacy type'.format(u))
            user['group'] = c.return_effective_value('service snmp v3 user {0} group'.format(u))

            data['user'].append(user)

    if c.exists_effective('service snmp v3 view'):
        for v in c.list_effective_nodes('service snmp v3 view'):
            view = {
                'name': v,
                'oids': []
            }
            view['oids'] = c.list_effective_nodes('service snmp v3 view {0} oid'.format(v))

            data['view'].append(view)

    if c.exists_effective('service snmp v3 trap-target'):
        for t in c.list_effective_nodes('service snmp v3 trap-target'):
            trap = {
                'name' : t,
                'port' : '',
                'proto': '',
                'auth' : '',
                'priv' : '',
                'type' : '',
                'engID': '',
                'user' : ''
            }
            trap['port']  = c.return_effective_value('service snmp v3 trap-target {0} port'.format(t))
            trap['proto'] = c.return_effective_value('service snmp v3 trap-target {0} protocol'.format(t))
            trap['auth']  = c.return_effective_value('service snmp v3 trap-target {0} auth type'.format(t))
            trap['priv']  = c.return_effective_value('service snmp v3 trap-target {0} privacy type'.format(t))
            trap['type']  = c.return_effective_value('service snmp v3 trap-target {0} type'.format(t))
            trap['engID'] = c.return_effective_value('service snmp v3 trap-target {0} engineid'.format(t))
            trap['user']  = c.return_effective_value('service snmp v3 trap-target {0} user'.format(t))

            data['trap'].append(trap)

    if args.all:
         # Special case, print all templates !
         tmpl = jinja2.Template(GROUP_OUTP_TMPL_SRC)
         print(tmpl.render(data))
         tmpl = jinja2.Template(TRAPTGT_OUTP_TMPL_SRC)
         print(tmpl.render(data))
         tmpl = jinja2.Template(USER_OUTP_TMPL_SRC)
         print(tmpl.render(data))
         tmpl = jinja2.Template(VIEW_OUTP_TMPL_SRC)
         print(tmpl.render(data))

    elif args.group:
         tmpl = jinja2.Template(GROUP_OUTP_TMPL_SRC)
         print(tmpl.render(data))

    elif args.trap:
         tmpl = jinja2.Template(TRAPTGT_OUTP_TMPL_SRC)
         print(tmpl.render(data))

    elif args.user:
         tmpl = jinja2.Template(USER_OUTP_TMPL_SRC)
         print(tmpl.render(data))

    elif args.view:
         tmpl = jinja2.Template(VIEW_OUTP_TMPL_SRC)
         print(tmpl.render(data))

    else:
        parser.print_help()

    sys.exit(1)
