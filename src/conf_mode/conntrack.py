#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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

from sys import exit

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.util import cmd
from vyos.util import run
from vyos.util import process_named_running
from vyos.template import render
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

conntrack_config = r'/etc/modprobe.d/vyatta_nf_conntrack.conf'
sysctl_file = r'/run/sysctl/10-vyos-conntrack.conf'

def resync_conntrackd():
    tmp = run('/usr/libexec/vyos/conf_mode/conntrack_sync.py')
    if tmp > 0:
        print('ERROR: error restarting conntrackd!')

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'conntrack']

    conntrack = conf.get_config_dict(base, key_mangling=('-', '_'),
                                     get_first_key=True)

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)
    conntrack = dict_merge(default_values, conntrack)

    return conntrack

def verify(conntrack):
    return None

def generate(conntrack):
    render(conntrack_config, 'conntrack/vyos_nf_conntrack.conf.tmpl', conntrack)
    render(sysctl_file, 'conntrack/sysctl.conf.tmpl', conntrack)

    return None

def apply(conntrack):
    if process_named_running('conntrackd'):
        # Reload conntrack-sync daemon to fetch new sysctl values
        resync_conntrackd()

    # We silently ignore all errors
    # See: https://bugzilla.redhat.com/show_bug.cgi?id=1264080
    cmd(f'sysctl -f {sysctl_file}')

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
