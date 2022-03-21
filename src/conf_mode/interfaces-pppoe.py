#!/usr/bin/env python3
#
# Copyright (C) 2019-2021 VyOS maintainers and contributors
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
from vyos.configdict import get_interface_dict
from vyos.configdict import leaf_node_changed
from vyos.configverify import verify_authentication
from vyos.configverify import verify_source_interface
from vyos.configverify import verify_interface_exists
from vyos.configverify import verify_vrf
from vyos.configverify import verify_mtu_ipv6
from vyos.configverify import verify_redirect
from vyos.ifconfig import PPPoEIf
from vyos.template import render
from vyos.util import call
from vyos.util import is_systemd_service_running
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
    base = ['interfaces', 'pppoe']
    pppoe = get_interface_dict(conf, base)

    # We should only terminate the PPPoE session if critical parameters change.
    # All parameters that can be changed on-the-fly (like interface description)
    # should not lead to a reconnect!
    tmp = leaf_node_changed(conf, ['access-concentrator'])
    if tmp: pppoe.update({'shutdown_required': {}})

    tmp = leaf_node_changed(conf, ['connect-on-demand'])
    if tmp: pppoe.update({'shutdown_required': {}})

    tmp = leaf_node_changed(conf, ['service-name'])
    if tmp: pppoe.update({'shutdown_required': {}})

    tmp = leaf_node_changed(conf, ['source-interface'])
    if tmp: pppoe.update({'shutdown_required': {}})

    tmp = leaf_node_changed(conf, ['vrf'])
    # leaf_node_changed() returns a list, as VRF is a non-multi node, there
    # will be only one list element
    if tmp: pppoe.update({'vrf_old': tmp[0]})

    tmp = leaf_node_changed(conf, ['authentication', 'user'])
    if tmp: pppoe.update({'shutdown_required': {}})

    tmp = leaf_node_changed(conf, ['authentication', 'password'])
    if tmp: pppoe.update({'shutdown_required': {}})

    return pppoe

def verify(pppoe):
    if 'deleted' in pppoe:
        # bail out early
        return None

    verify_source_interface(pppoe)
    verify_authentication(pppoe)
    verify_vrf(pppoe)
    verify_mtu_ipv6(pppoe)
    verify_redirect(pppoe)

    if {'connect_on_demand', 'vrf'} <= set(pppoe):
        raise ConfigError('On-demand dialing and VRF can not be used at the same time')

    return None

def generate(pppoe):
    # set up configuration file path variables where our templates will be
    # rendered into
    ifname = pppoe['ifname']
    config_pppoe = f'/etc/ppp/peers/{ifname}'

    if 'deleted' in pppoe or 'disable' in pppoe:
        if os.path.exists(config_pppoe):
            os.unlink(config_pppoe)

        return None

    # Create PPP configuration files
    render(config_pppoe, 'pppoe/peer.tmpl', pppoe, permission=0o640)

    return None

def apply(pppoe):
    ifname = pppoe['ifname']
    if 'deleted' in pppoe or 'disable' in pppoe:
        if os.path.isdir(f'/sys/class/net/{ifname}'):
            p = PPPoEIf(ifname)
            p.remove()
        call(f'systemctl stop ppp@{ifname}.service')
        return None

    # reconnect should only be necessary when certain config options change,
    # like ACS name, authentication, no-peer-dns, source-interface
    if ((not is_systemd_service_running(f'ppp@{ifname}.service')) or
        'shutdown_required' in pppoe):

        # cleanup system (e.g. FRR routes first)
        if os.path.isdir(f'/sys/class/net/{ifname}'):
            p = PPPoEIf(ifname)
            p.remove()

        call(f'systemctl restart ppp@{ifname}.service')
    else:
        if os.path.isdir(f'/sys/class/net/{ifname}'):
            p = PPPoEIf(ifname)
            p.update(pppoe)

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
