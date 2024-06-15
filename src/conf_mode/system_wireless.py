#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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
from vyos.configdep import set_dependents
from vyos.configdep import call_dependents
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'wireless']
    interface_base = ['interfaces', 'wireless']

    wireless = conf.get_config_dict(base, key_mangling=('-', '_'),
                                    get_first_key=True)


    if conf.exists(interface_base):
        wireless['interfaces'] = conf.list_nodes(interface_base)
        for interface in wireless['interfaces']:
            set_dependents('wireless', conf, interface)

    return wireless

def verify(wireless):
    pass

def generate(wireless):
    pass

def apply(wireless):
    if 'interfaces' in wireless:
        call_dependents()
    pass

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
