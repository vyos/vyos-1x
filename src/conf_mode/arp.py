#!/usr/bin/env python3
#
# Copyright (C) 2018-2022 VyOS maintainers and contributors
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
from vyos.configdict import node_changed
from vyos.util import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['protocols', 'static', 'arp']
    arp = conf.get_config_dict(base)
    tmp = node_changed(conf, base)
    if tmp: arp.update({'removed' : node_changed(conf, base)})

    return arp

def verify(arp):
    pass

def generate(arp):
    pass

def apply(arp):
    if not arp:
        return None

    if 'removed' in arp:
        for host in arp['removed']:
            call(f'arp --delete {host}')

    if 'arp' in arp:
        for host, host_config in arp['arp'].items():
            mac = host_config['hwaddr']
            call(f'arp --set {host} {mac}')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
