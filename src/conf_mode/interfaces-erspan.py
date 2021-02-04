#!/usr/bin/env python3
#
# Copyright (C) 2018-2020 VyOS maintainers and contributors
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
from netifaces import interfaces

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configdict import get_interface_dict
from vyos.configdict import node_changed
from vyos.configdict import leaf_node_changed
from vyos.configverify import verify_mtu_ipv6
from vyos.configverify import verify_tunnel
from vyos.ifconfig import Interface
from vyos.ifconfig import ERSpanIf
from vyos.ifconfig import ER6SpanIf
from vyos.template import is_ipv4
from vyos.template import is_ipv6
from vyos.util import dict_search
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least
    the interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'erspan']
    erspan = get_interface_dict(conf, base)
    
    tmp = leaf_node_changed(conf, ['encapsulation'])
    if tmp:
        erspan.update({'encapsulation_changed': {}})

    return erspan

def verify(erspan):
    if 'deleted' in erspan:
        return None
    
    if 'encapsulation' not in erspan:
        raise ConfigError('Unable to detect the following ERSPAN tunnel encapsulation'\
                          '{ifname}!'.format(**erspan))

    verify_mtu_ipv6(erspan)
    verify_tunnel(erspan)
    
    key = dict_search('parameters.ip.key',erspan)
    if key == None:
        raise ConfigError('parameters.ip.key is mandatory for ERSPAN tunnel')
            

def generate(erspan):
    return None

def apply(erspan):
    if 'deleted' in erspan or 'encapsulation_changed' in erspan: 
        if erspan['ifname'] in interfaces(): 
            tmp = Interface(erspan['ifname']) 
            tmp.remove() 
        if 'deleted' in erspan: 
            return None 
    
    dispatch = {
        'erspan': ERSpanIf,
        'ip6erspan': ER6SpanIf
    }

    # We need to re-map the tunnel encapsulation proto to a valid interface class
    encap = erspan['encapsulation']
    klass = dispatch[encap]
    
    conf = deepcopy(erspan)
    
    conf.update(klass.get_config())
    
    del conf['ifname']
    
    erspan_tunnel = klass(erspan['ifname'],**conf)
    erspan_tunnel.change_options()
    erspan_tunnel.update(erspan)

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        generate(c)
        verify(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
