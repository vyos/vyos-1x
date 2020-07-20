#!/usr/bin/env python3
#
# Copyright (C) 2019-2020 VyOS maintainers and contributors
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

from copy import deepcopy
from sys import exit

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configdict import leaf_node_changed
from vyos.configverify import verify_vrf
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_source_interface
from vyos.configverify import verify_vlan_config
from vyos.ifconfig import MACVLANIf
from vyos import ConfigError

from vyos import airbag
airbag.enable()

def get_config():
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    conf = Config()
    base = ['interfaces', 'pseudo-ethernet']

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    ifname = os.environ['VYOS_TAGNODE_VALUE']
    peth = get_interface_dict(conf, base, ifname)

    mode = leaf_node_changed(conf, ['mode'])
    if mode:
        peth.update({'mode_old' : mode})

    return peth

def verify(peth):
    if 'deleted' in peth:
        verify_bridge_delete(peth)
        return None

    verify_source_interface(peth)
    verify_vrf(peth)
    verify_address(peth)

    # use common function to verify VLAN configuration
    verify_vlan_config(peth)
    return None

def generate(peth):
    return None

def apply(peth):
    if 'deleted' in peth:
        # delete interface
        MACVLANIf(peth['ifname']).remove()
        return None

    # Check if MACVLAN interface already exists. Parameters like the underlaying
    # source-interface device or mode can not be changed on the fly and the interface
    # needs to be recreated from the bottom.
    if 'mode_old' in peth:
        MACVLANIf(peth['ifname']).remove()

    # MACVLAN interface needs to be created on-block instead of passing a ton
    # of arguments, I just use a dict that is managed by vyos.ifconfig
    conf = deepcopy(MACVLANIf.get_config())

    # Assign MACVLAN instance configuration parameters to config dict
    conf['source_interface'] = peth['source_interface']
    conf['mode'] = peth['mode']

    # It is safe to "re-create" the interface always, there is a sanity check
    # that the interface will only be create if its non existent
    p = MACVLANIf(peth['ifname'], **conf)
    p.update(peth)
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
