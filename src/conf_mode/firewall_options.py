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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import sys
import os
import copy

from vyos.config import Config
from vyos import ConfigError

default_config_data = {
    'intf_opts': [],
    'new_chain4': False,
    'new_chain6': False
}

def get_config():
    opts = copy.deepcopy(default_config_data)
    conf = Config()
    if not conf.exists('firewall options'):
        return None
    else:
        conf.set_level('firewall options')

        # Parse configuration of each individual instance
        if conf.exists('interface'):
            for intf in conf.list_nodes('interface'):
                conf.set_level('firewall options interface {0}'.format(intf))
                config = {
                    'intf': intf,
                    'disabled': False,
                    'mss4': '',
                    'mss6': ''
                }

                # Check if individual option is disabled
                if conf.exists('disable'):
                    config['disabled'] = True

                #
                # Get MSS value IPv4
                #
                if conf.exists('adjust-mss'):
                    config['mss4'] = conf.return_value('adjust-mss')

                    # We need a marker that a new iptables chain needs to be generated
                    if not opts['new_chain4']:
                        opts['new_chain4'] = True

                #
                # Get MSS value IPv6
                #
                if conf.exists('adjust-mss6'):
                    config['mss6'] = conf.return_value('adjust-mss6')

                    # We need a marker that a new ip6tables chain needs to be generated
                    if not opts['new_chain6']:
                        opts['new_chain6'] = True

                # Append interface options to global list
                opts['intf_opts'].append(config)

    return opts

def verify(tcp):
    # syntax verification is done via cli
    return None

def apply(tcp):
    target = 'VYOS_FW_OPTIONS'

    # always cleanup iptables
    os.system('iptables --table mangle --delete FORWARD --jump {} >&/dev/null'.format(target))
    os.system('iptables --table mangle --flush {} >&/dev/null'.format(target))
    os.system('iptables --table mangle --delete-chain {} >&/dev/null'.format(target))

    # always cleanup ip6tables
    os.system('ip6tables --table mangle --delete FORWARD --jump {} >&/dev/null'.format(target))
    os.system('ip6tables --table mangle --flush {} >&/dev/null'.format(target))
    os.system('ip6tables --table mangle --delete-chain {} >&/dev/null'.format(target))

    # Setup new iptables rules
    if tcp['new_chain4']:
        os.system('iptables --table mangle --new-chain {} >&/dev/null'.format(target))
        os.system('iptables --table mangle --append FORWARD --jump {} >&/dev/null'.format(target))

        for opts in tcp['intf_opts']:
            intf = opts['intf']
            mss = opts['mss4']

            # Check if this rule iis disabled
            if opts['disabled']:
                continue

            # adjust TCP MSS per interface
            if mss:
                os.system('iptables --table mangle --append {} --out-interface {} --protocol tcp ' \
                          '--tcp-flags SYN,RST SYN --jump TCPMSS --set-mss {} >&/dev/null'.format(target, intf, mss))

    # Setup new ip6tables rules
    if tcp['new_chain6']:
        os.system('ip6tables --table mangle --new-chain {} >&/dev/null'.format(target))
        os.system('ip6tables --table mangle --append FORWARD --jump {} >&/dev/null'.format(target))

        for opts in tcp['intf_opts']:
            intf = opts['intf']
            mss = opts['mss6']

            # Check if this rule iis disabled
            if opts['disabled']:
                continue

            # adjust TCP MSS per interface
            if mss:
                os.system('ip6tables --table mangle --append {} --out-interface {} --protocol tcp ' \
                          '--tcp-flags SYN,RST SYN --jump TCPMSS --set-mss {} >&/dev/null'.format(target, intf, mss))

    return None

if __name__ == '__main__':

    try:
        c = get_config()
        verify(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
