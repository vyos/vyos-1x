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

import os

from sys import exit
from copy import deepcopy

from vyos import ConfigError
from vyos.config import Config
from vyos.util import call
from vyos.template import render

from vyos import airbag
airbag.enable()

config_file = r'/tmp/ripd.frr'

def get_config():
    conf = Config()
    rip_conf = {
        'rip_conf' : False,
        'old_rip'  : {
            'neighbors'  : {},
            'networks'    : {},
            'ifaces'     : {}
        },
        'rip'  : {
            'neighbors'  : {},
            'networks'    : {},
            'ifaces'     : {}
        }
    }

    if not (conf.exists('protocols nrip') or conf.exists_effective('protocols nrip')):
        return None

    if conf.exists('protocols nrip'):
        rip_conf['rip_conf'] = True

    conf.set_level('protocols nrip')


#    if conf_mode == "effective" and conf.exists_effective('network'):
#        rip_conf['old_rip']['networks'] = conf.return_effective_value('network')
    
#    if conf_mode == "proposed" and conf.exists('network'):
#        rip_conf['rip']['networks'] = conf.return_value('network')

    # Get networks
    for network in conf.list_effective_nodes('network'):
        rip_conf['old_rip']['networks'] = conf.return_effective_value('network')

    for network in conf.list_nodes('network'):
        rip_conf['rip']['networks'] = conf.return_value('network')

#    for net in conf.list_effective_nodes('network'):
#        rip_conf['old_rip']['networks'][rip_net] = conf.return_effective_value('network {0} '.format(rip_net))
#
#    for net in conf.list_nodes('network'):
#        rip_conf['rip']['networks'][rip_net] = conf.return_value('network {0} '.format(rip_net))

    print(rip_conf)
    return rip_conf



def verify(rip):
    if rip is None:
        return None

    conf = Config()


def generate(rip):
    if rip is None:
        return None

    render(config_file, 'frr/rip.frr.tmpl', rip)
    return None

def apply(rip):
    if rip is None:
        return None

    if os.path.exists(config_file):
        call("sudo vtysh -d ripd -f " + config_file)
 #       os.remove(config_file)

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
