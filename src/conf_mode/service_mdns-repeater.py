#!/usr/bin/env python3
#
# Copyright (C) 2017-2020 VyOS maintainers and contributors
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

from sys import exit
from netifaces import ifaddresses, interfaces, AF_INET

from vyos.config import Config
from vyos.template import render
from vyos.util import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = r'/etc/default/mdns-repeater'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'mdns', 'repeater']
    mdns = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    return mdns

def verify(mdns):
    if not mdns:
        return None

    if 'disable' in mdns:
        return None

    # We need at least two interfaces to repeat mDNS advertisments
    if 'interface' not in mdns or len(mdns['interface']) < 2:
        raise ConfigError('mDNS repeater requires at least 2 configured interfaces!')

    # For mdns-repeater to work it is essential that the interfaces has
    # an IPv4 address assigned
    for interface in mdns['interface']:
        if interface not in interfaces():
            raise ConfigError(f'Interface "{interface}" does not exist!')

        if AF_INET not in ifaddresses(interface):
            raise ConfigError('mDNS repeater requires an IPv4 address to be '
                                  f'configured on interface "{interface}"')

    return None

def generate(mdns):
    if not mdns:
        return None

    if 'disable' in mdns:
        print('Warning: mDNS repeater will be deactivated because it is disabled')
        return None

    render(config_file, 'mdns-repeater/mdns-repeater.tmpl', mdns)
    return None

def apply(mdns):
    if not mdns or 'disable' in mdns:
        call('systemctl stop mdns-repeater.service')
        if os.path.exists(config_file):
            os.unlink(config_file)
    else:
        call('systemctl restart mdns-repeater.service')

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
