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
from copy import deepcopy
from netifaces import ifaddresses, AF_INET

from vyos.config import Config
from vyos import ConfigError
from vyos.util import call
from vyos.template import render


config_file = r'/etc/default/mdns-repeater'

default_config_data = {
    'disabled': False,
    'interfaces': []
}

def get_config():
    mdns = deepcopy(default_config_data)
    conf = Config()
    base = ['service', 'mdns', 'repeater']
    if not conf.exists(base):
        return None
    else:
        conf.set_level(base)

    # Service can be disabled by user
    if conf.exists(['disable']):
        mdns['disabled'] = True
        return mdns

    # Interface to repeat mDNS advertisements
    if conf.exists(['interface']):
        mdns['interfaces'] = conf.return_values(['interface'])

    return mdns

def verify(mdns):
    if mdns is None:
        return None

    if mdns['disabled']:
        return None

    # We need at least two interfaces to repeat mDNS advertisments
    if len(mdns['interfaces']) < 2:
        raise ConfigError('mDNS repeater requires at least 2 configured interfaces!')

    # For mdns-repeater to work it is essential that the interfaces has
    # an IPv4 address assigned
    for interface in mdns['interfaces']:
        if AF_INET in ifaddresses(interface).keys():
            if len(ifaddresses(interface)[AF_INET]) < 1:
                raise ConfigError('mDNS repeater requires an IPv6 address configured on interface %s!'.format(interface))

    return None

def generate(mdns):
    if mdns is None:
        return None

    if mdns['disabled']:
        print('Warning: mDNS repeater will be deactivated because it is disabled')
        return None

    render(config_file, 'mdns-repeater/mdns-repeater.tmpl', mdns)
    return None

def apply(mdns):
    if (mdns is None) or mdns['disabled']:
        call('sudo systemctl stop mdns-repeater')
        if os.path.exists(config_file):
            os.unlink(config_file)
    else:
        call('sudo systemctl restart mdns-repeater')

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
