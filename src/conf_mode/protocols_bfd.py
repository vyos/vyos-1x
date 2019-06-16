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

import sys
import copy
import vyos.validate

from vyos import ConfigError
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
            'remote': peer,
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

    return bfd

def verify(bfd):
    if bfd is None:
        return None

    for peer in bfd['peers']:
        # Bail out early if peer is shutdown
        if peer['shutdown']:
            continue

        # IPv6 peers require an explicit local address/interface combination
        if vyos.validate.is_ipv6(peer['remote']):
            if not (peer['local-interface'] and peer['local-address']):
                raise ConfigError("BFD IPv6 peers require explicit local address/interface setting")


    return None

def generate(bfd):
    if bfd is None:
        return None

    return None

def apply(bfd):
    if bfd is None:
        return None

    print(bfd)
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
