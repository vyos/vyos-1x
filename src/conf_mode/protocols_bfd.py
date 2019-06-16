#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
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

import copy
from vyos.config import Config

default_config_data = {
    'peers': []
}

def get_config():
    bfd = copy.deepcopy(default_config_data)
    conf = Config()
    if not conf.exists('protocols bfd'):
        return None
    else:
        conf.set_level('protocols bfd')

    for peer in conf.list_nodes('peer'):
        conf.set_level('protocols bfd peer {0}'.format(peer))
        bfd_peer = {
            'peer': peer,
            'shutdown': False,
            'local-interface': '',
            'local-address': '',
        }

        # Check if individual peer is disabled
        if conf.exists('shutdown'):
            bfd_peer['shutdown'] = True

        # Check if peer has a local source interface configured
        if conf.exists('local-interface'):
            bfd_peer['local-interface'] = conf.return_value('local-interface')

        # Check if peer has a local source address configured - this is mandatory for IPv6
        if conf.exists('local-address'):
            bfd_peer['local-address'] = conf.return_value('local-address')

        bfd['peers'].append(bfd_peer)

    print(bfd)
    return bfd

def verify(bfd):
    return None

def generate(bfd):
    return None

def apply(bfd):
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
