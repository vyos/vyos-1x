#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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

from netifaces import interfaces
from sys import exit

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.ifconfig import VTIIf
from vyos.util import dict_search
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'vti']
    vti = get_interface_dict(conf, base)

    # VTI is more then an interface - we retrieve the "real" configuration from
    # the IPsec peer configuration which binds this VTI
    conf.set_level([])
    vti['ipsec'] = conf.get_config_dict(['vpn', 'ipsec', 'site-to-site', 'peer'],
                               key_mangling=('-', '_'), get_first_key=True,
                               no_tag_node_value_mangle=True)

    for peer, peer_config in vti['ipsec'].items():
        if dict_search('vti.bind', peer_config) == vti['ifname']:
            vti['remote'] = peer
            if 'local_address' in peer_config:
                vti['source_address'] = peer_config['local_address']
            # we also need to "calculate" a per vti individual key
            base = 0x900000
            vti['key'] = base + int(vti['ifname'].lstrip('vti'))

    return vti

def verify(vti):
    if 'deleted' in vti:
        return None

    ifname = vti['ifname']
    found = False
    for peer, peer_config in vti['ipsec'].items():
        if dict_search('vti.bind', peer_config) == ifname:
            found = True
            # we can now stop processing the for loop
            break
    if not found:
        tmp = vti['ifname']
        raise ConfigError(f'Interface "{ifname}" not referenced in any VPN configuration!')

    return None

def generate(vti):
    return None

def apply(vti):
    if vti['ifname'] in interfaces():
        # Always delete the VTI interface in advance
        VTIIf(**vti).remove()

    if 'deleted' not in vti:
        tmp = VTIIf(**vti)
        tmp.update(vti)

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
