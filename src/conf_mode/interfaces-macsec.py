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

from copy import deepcopy
from sys import exit
from netifaces import interfaces

from vyos.config import Config
from vyos.configdict import list_diff
from vyos.ifconfig import MACsecIf, Interface
from vyos.template import render
from vyos.util import call
from vyos.validate import is_member
from vyos import ConfigError

default_config_data = {
    'address': [],
    'address_remove': [],
    'deleted': False,
    'description': '',
    'disable': False,
    'security_cipher': '',
    'security_encrypt': False,
    'security_mka_cak': '',
    'security_mka_ckn': '',
    'security_mka_priority': '255',
    'intf': '',
    'source_interface': '',
    'is_bridge_member': False,
    'vrf': ''
}

def get_config():
    macsec = deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    macsec['intf'] = os.environ['VYOS_TAGNODE_VALUE']
    base_path = ['interfaces', 'macsec', macsec['intf']]

    # check if we are a member of any bridge
    macsec['is_bridge_member'] = is_member(conf, macsec['intf'], 'bridge')

    # Check if interface has been removed
    if not conf.exists(base_path):
        macsec['deleted'] = True
        return macsec

    # set new configuration level
    conf.set_level(base_path)

    # retrieve configured interface addresses
    if conf.exists(['address']):
        macsec['address'] = conf.return_values(['address'])

    # retrieve interface description
    if conf.exists(['description']):
        macsec['description'] = conf.return_value(['description'])

    # Disable this interface
    if conf.exists(['disable']):
        macsec['disable'] = True

    # retrieve interface cipher
    if conf.exists(['security', 'cipher']):
        macsec['security_cipher'] = conf.return_value(['security', 'cipher'])

    # Enable optional MACsec encryption
    if conf.exists(['security', 'encrypt']):
        macsec['security_encrypt'] = True

    # Secure Connectivity Association Key
    if conf.exists(['security', 'mka', 'cak']):
        macsec['security_mka_cak'] = conf.return_value(['security', 'mka', 'cak'])

    # Secure Connectivity Association Name
    if conf.exists(['security', 'mka', 'ckn']):
        macsec['security_mka_ckn'] = conf.return_value(['security', 'mka', 'ckn'])

    # MACsec Key Agreement protocol (MKA) actor priority
    if conf.exists(['security', 'mka', 'priority']):
        macsec['security_mka_priority'] = conf.return_value(['security', 'mka', 'priority'])

    # Physical interface
    if conf.exists(['source-interface']):
        macsec['source_interface'] = conf.return_value(['source-interface'])

    # Determine interface addresses (currently effective) - to determine which
    # address is no longer valid and needs to be removed from the interface
    eff_addr = conf.return_effective_values(['address'])
    act_addr = conf.return_values(['address'])
    macsec['address_remove'] = list_diff(eff_addr, act_addr)

    # retrieve VRF instance
    if conf.exists(['vrf']):
        macsec['vrf'] = conf.return_value(['vrf'])

    return macsec

def verify(macsec):
    if macsec['deleted']:
        if macsec['is_bridge_member']:
            raise ConfigError(
                f'Interface "{intf}" cannot be deleted as it is a '
                f'member of bridge "{is_bridge_member}"!'.format(**macsec))

        return None

    if not macsec['source_interface']:
        raise ConfigError(
            'Physical source interface must be set for MACsec "{intf}"'.format(**macsec))

    if not macsec['security_cipher']:
        raise ConfigError(
            'Cipher suite must be set for MACsec "{intf}"'.format(**macsec))

    if macsec['security_encrypt']:
        if not (macsec['security_mka_cak'] and macsec['security_mka_ckn']):
            raise ConfigError('MACsec security keys mandartory when encryption is enabled')

    if macsec['vrf']:
        if macsec['vrf'] not in interfaces():
            raise ConfigError('VRF "{vrf}" does not exist'.format(**macsec))

        if macsec['is_bridge_member']:
            raise ConfigError(
                'Interface "{intf}" cannot be member of VRF "{vrf}" and '
                'bridge "{is_bridge_member}" at the same time!'.format(**macsec))

    if macsec['is_bridge_member'] and macsec['address']:
        raise ConfigError(
            'Cannot assign address to interface "{intf}" as it is'
            'a member of bridge "{is_bridge_member}"!'.format(**macsec))

    return None

def generate(macsec):
    # XXX: wpa_supplicant works on the source interface not the resulting
    #      MACsec interface
    wpa_suppl_conf = '/run/wpa_supplicant/{source_interface}.conf'
    conf = wpa_suppl_conf.format(**macsec)

    render(conf, 'macsec/wpa_supplicant.conf.tmpl', macsec, permission=0o640)
    return None

def apply(macsec):
    # Remove macsec interface
    if macsec['deleted']:
        call('systemctl stop wpa_supplicant-macsec@{intf}.service'.format(**macsec))
        MACsecIf(macsec['intf']).remove()

    else:
        # MACsec interfaces require a configuration when they are added using
        # iproute2. This static method will provide the configuration
        # dictionary used by this class.
        conf = deepcopy(MACsecIf.get_config())

        # Assign MACsec instance configuration parameters to config dict
        conf['source_interface'] = macsec['source_interface']
        conf['security_cipher'] = macsec['security_cipher']

        # It is safe to "re-create" the interface always, there is a sanity check
        # that the interface will only be create if its non existent
        i = MACsecIf(macsec['intf'], **conf)

        # update interface description used e.g. within SNMP
        i.set_alias(macsec['description'])

        # Configure interface address(es)
        # - not longer required addresses get removed first
        # - newly addresses will be added second
        for addr in macsec['address_remove']:
            i.del_addr(addr)
        for addr in macsec['address']:
            i.add_addr(addr)

        # assign/remove VRF (ONLY when not a member of a bridge,
        # otherwise 'nomaster' removes it from it)
        if not macsec['is_bridge_member']:
            i.set_vrf(macsec['vrf'])

        # Interface is administratively down by default, enable if desired
        if not macsec['disable']:
            i.set_admin_state('up')

        call('systemctl restart wpa_supplicant-macsec@{source_interface}.service'.format(**macsec))

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
