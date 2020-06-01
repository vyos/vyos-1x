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

import jmespath

from copy import deepcopy
from sys import exit

from vyos.config import Config
from vyos.template import render
from vyos import ConfigError, airbag
airbag.enable()

config_file = r'/tmp/bgp.frr'

default_config_data = {
    'as_number':  ''
}

def get_config():
    bgp = deepcopy(default_config_data)
    conf = Config()

    # this lives in the "nbgp" tree until we switch over
    base = ['protocols', 'nbgp']
    if not conf.exists(base):
        return None

    bgp = deepcopy(default_config_data)
    # Get full BGP configuration as dictionary - output the configuration for development
    #
    # vyos@vyos# commit
    # [ protocols nbgp 65000 ]
    # {'nbgp': {'65000': {'address-family': {'ipv4-unicast': {'aggregate-address': {'1.1.0.0/16': {},
    #                                                                               '2.2.2.0/24': {}}},
    #                                        'ipv6-unicast': {'aggregate-address': {'2001:db8::/32': {}}}},
    #                     'neighbor': {'192.0.2.1': {'password': 'foo',
    #                                                'remote-as': '100'}}}}}
    #
    tmp = conf.get_config_dict(base)

    # extract base key from dict as this is our AS number
    bgp['as_number'] = jmespath.search('nbgp | keys(@) [0]', tmp)

    # adjust level of dictionary returned by get_config_dict()
    # by using jmesgpath and update dictionary
    bgp.update(jmespath.search('nbgp.* | [0]', tmp))

    from pprint import pprint
    pprint(bgp)
    # resulting in e.g.
    # vyos@vyos# commit
    # [ protocols nbgp 65000 ]
    # {'address-family': {'ipv4-unicast': {'aggregate-address': {'1.1.0.0/16': {},
    #                                                            '2.2.2.0/24': {}}},
    #                     'ipv6-unicast': {'aggregate-address': {'2001:db8::/32': {}}}},
    #  'as_number': '65000',
    #  'neighbor': {'192.0.2.1': {'password': 'foo', 'remote-as': '100'}},
    #  'timers': {'holdtime': '5'}}

    return bgp

def verify(bgp):
    # bail out early - looks like removal from running config
    if not bgp:
        return None

    return None

def generate(bgp):
    # bail out early - looks like removal from running config
    if not bgp:
        return None

    render(config_file, 'frr/bgp.frr.tmpl', bgp)
    return None

def apply(bgp):
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
