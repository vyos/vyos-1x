#!/usr/bin/env python3
#
# Copyright (C) 2020-2022 VyOS maintainers and contributors
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

from netifaces import interfaces
from sys import exit

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configdict import is_node_changed
from vyos.configdict import is_source_interface
from vyos.configverify import verify_vrf
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_mtu_ipv6
from vyos.configverify import verify_mirror_redirect
from vyos.configverify import verify_source_interface
from vyos.configverify import verify_bond_bridge_member
from vyos.ifconfig import MACsecIf
from vyos.ifconfig import Interface
from vyos.template import render
from vyos.util import call
from vyos.util import dict_search
from vyos.util import is_systemd_service_running
from vyos import ConfigError
from vyos import airbag
airbag.enable()

# XXX: wpa_supplicant works on the source interface
wpa_suppl_conf = '/run/wpa_supplicant/{source_interface}.conf'

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'macsec']
    ifname, macsec = get_interface_dict(conf, base)

    # Check if interface has been removed
    if 'deleted' in macsec:
        source_interface = conf.return_effective_value(base + [ifname, 'source-interface'])
        macsec.update({'source_interface': source_interface})

    if is_node_changed(conf, base + [ifname, 'security']):
        macsec.update({'shutdown_required': {}})

    if is_node_changed(conf, base + [ifname, 'source_interface']):
        macsec.update({'shutdown_required': {}})

    if 'source_interface' in macsec:
        tmp = is_source_interface(conf, macsec['source_interface'], ['macsec', 'pseudo-ethernet'])
        if tmp and tmp != ifname: macsec.update({'is_source_interface' : tmp})

    return macsec


def verify(macsec):
    if 'deleted' in macsec:
        verify_bridge_delete(macsec)
        return None

    verify_source_interface(macsec)
    verify_vrf(macsec)
    verify_mtu_ipv6(macsec)
    verify_address(macsec)
    verify_bond_bridge_member(macsec)
    verify_mirror_redirect(macsec)

    if dict_search('security.cipher', macsec) == None:
        raise ConfigError('Cipher suite must be set for MACsec "{ifname}"'.format(**macsec))

    if dict_search('security.encrypt', macsec) != None:
        if dict_search('security.mka.cak', macsec) == None or dict_search('security.mka.ckn', macsec) == None:
            raise ConfigError('Missing mandatory MACsec security keys as encryption is enabled!')

        cak_len = len(dict_search('security.mka.cak', macsec))

        if dict_search('security.cipher', macsec) == 'gcm-aes-128' and cak_len != 32:
            # gcm-aes-128 requires a 128bit long key - 32 characters (string) = 16byte = 128bit
            raise ConfigError('gcm-aes-128 requires a 128bit long key!')

        elif dict_search('security.cipher', macsec) == 'gcm-aes-256' and cak_len != 64:
            # gcm-aes-128 requires a 128bit long key - 64 characters (string) = 32byte = 256bit
            raise ConfigError('gcm-aes-128 requires a 256bit long key!')

    if 'source_interface' in macsec:
        # MACsec adds a 40 byte overhead (32 byte MACsec + 8 bytes VLAN 802.1ad
        # and 802.1q) - we need to check the underlaying MTU if our configured
        # MTU is at least 40 bytes less then the MTU of our physical interface.
        lower_mtu = Interface(macsec['source_interface']).get_mtu()
        if lower_mtu < (int(macsec['mtu']) + 40):
            raise ConfigError('MACsec overhead does not fit into underlaying device MTU,\n' \
                              f'{lower_mtu} bytes is too small!')

    return None


def generate(macsec):
    render(wpa_suppl_conf.format(**macsec), 'macsec/wpa_supplicant.conf.j2', macsec)
    return None


def apply(macsec):
    systemd_service = 'wpa_supplicant-macsec@{source_interface}'.format(**macsec)

    # Remove macsec interface on deletion or mandatory parameter change
    if 'deleted' in macsec or 'shutdown_required' in macsec:
        call(f'systemctl stop {systemd_service}')

        if macsec['ifname'] in interfaces():
            tmp = MACsecIf(macsec['ifname'])
            tmp.remove()

        if 'deleted' in macsec:
            # delete configuration on interface removal
            if os.path.isfile(wpa_suppl_conf.format(**macsec)):
                os.unlink(wpa_suppl_conf.format(**macsec))

            return None

    # It is safe to "re-create" the interface always, there is a sanity
    # check that the interface will only be create if its non existent
    i = MACsecIf(**macsec)
    i.update(macsec)

    if not is_systemd_service_running(systemd_service) or 'shutdown_required' in macsec:
        call(f'systemctl reload-or-restart {systemd_service}')

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
