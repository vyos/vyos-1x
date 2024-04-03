#!/usr/bin/env python3
#
# Copyright (C) 2019-2024 VyOS maintainers and contributors
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
from vyos.configdict import get_interface_dict
from vyos.configdict import is_node_changed
from vyos.configdict import is_source_interface
from vyos.configdict import is_node_changed
from vyos.configverify import verify_vrf
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_source_interface
from vyos.configverify import verify_vlan_config
from vyos.configverify import verify_mtu_parent
from vyos.configverify import verify_mirror_redirect
from vyos.ifconfig import MACVLANIf
from vyos.utils.network import interface_exists
from vyos import ConfigError

from vyos import airbag
airbag.enable()

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at
    least the interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'pseudo-ethernet']
    ifname, peth = get_interface_dict(conf, base)

    mode = is_node_changed(conf, ['mode'])
    if mode: peth.update({'shutdown_required' : {}})

    if is_node_changed(conf, base + [ifname, 'mode']):
        peth.update({'rebuild_required': {}})

    if 'source_interface' in peth:
        _, peth['parent'] = get_interface_dict(conf, ['interfaces', 'ethernet'],
                                               peth['source_interface'])
        # test if source-interface is maybe already used by another interface
        tmp = is_source_interface(conf, peth['source_interface'], ['macsec'])
        if tmp and tmp != ifname: peth.update({'is_source_interface' : tmp})

    return peth

def verify(peth):
    if 'deleted' in peth:
        verify_bridge_delete(peth)
        return None

    verify_source_interface(peth)
    verify_vrf(peth)
    verify_address(peth)
    verify_mtu_parent(peth, peth['parent'])
    verify_mirror_redirect(peth)
    # use common function to verify VLAN configuration
    verify_vlan_config(peth)

    return None

def generate(peth):
    return None

def apply(peth):
    # Check if the MACVLAN interface already exists
    if 'rebuild_required' in peth or 'deleted' in peth:
        if interface_exists(peth['ifname']):
            p = MACVLANIf(**peth)
            # MACVLAN is always needs to be recreated,
            # thus we can simply always delete it first.
            p.remove()

    if 'deleted' not in peth:
        p = MACVLANIf(**peth)
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
