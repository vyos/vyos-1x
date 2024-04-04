#!/usr/bin/env python3
#
# Copyright (C) 2022-2024 VyOS maintainers and contributors
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

from vyos import ConfigError
from vyos import airbag
from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_vrf
from vyos.ifconfig import VethIf
from vyos.utils.network import interface_exists
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
    base = ['interfaces', 'virtual-ethernet']
    ifname, veth = get_interface_dict(conf, base)

    # We need to know all other veth related interfaces as veth requires a 1:1
    # mapping for the peer-names. The Linux kernel automatically creates both
    # interfaces, the local one and the peer-name, but VyOS also needs a peer
    # interfaces configrued on the CLI so we can assign proper IP addresses etc.
    veth['other_interfaces'] = conf.get_config_dict(base, key_mangling=('-', '_'),
                                     get_first_key=True, no_tag_node_value_mangle=True)

    return veth


def verify(veth):
    if 'deleted' in veth:
        verify_bridge_delete(veth)
        # Prevent to delete veth interface which used for another "vethX peer-name"
        for iface, iface_config in veth['other_interfaces'].items():
            if veth['ifname'] in iface_config['peer_name']:
                ifname = veth['ifname']
                raise ConfigError(
                    f'Cannot delete "{ifname}" used for "interface {iface} peer-name"'
                )
        return None

    verify_vrf(veth)
    verify_address(veth)

    if 'peer_name' not in veth:
        raise ConfigError(f'Remote peer name must be set for "{veth["ifname"]}"!')

    peer_name = veth['peer_name']
    ifname = veth['ifname']

    if veth['peer_name'] not in veth['other_interfaces']:
        raise ConfigError(f'Used peer-name "{peer_name}" on interface "{ifname}" ' \
                          'is not configured!')

    if veth['other_interfaces'][peer_name]['peer_name'] != ifname:
        raise ConfigError(
            f'Configuration mismatch between "{ifname}" and "{peer_name}"!')

    if peer_name == ifname:
        raise ConfigError(
            f'Peer-name "{peer_name}" cannot be the same as interface "{ifname}"!')

    return None


def generate(peth):
    return None

def apply(veth):
    # Check if the Veth interface already exists
    if 'rebuild_required' in veth or 'deleted' in veth:
        if interface_exists(veth['ifname']):
            p = VethIf(**veth)
            p.remove()

    if 'deleted' not in veth:
        p = VethIf(**veth)
        p.update(veth)

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
