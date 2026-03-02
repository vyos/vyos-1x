#!/usr/bin/env python3
#
# Copyright (C) VyOS Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from vyos import ConfigError

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configdep import set_dependents, call_dependents
from vyos.utils.process import is_systemd_service_active

from vyos.ifconfig.vpp import VPPLoopbackInterface


def get_config(config=None) -> dict:
    """Get Loopback interface configuration

    Args:
        config (vyos.config.Config, optional): The VyOS configuration dictionary
    Returns:
        dict: Loopback interface configuration
    """
    if config:
        conf = config
    else:
        conf = Config()

    base = ['interfaces', 'vpp', 'loopback']

    ifname, config = get_interface_dict(conf, base)

    if not conf.exists(['vpp']) and not conf.exists(base):
        config['remove_vpp'] = True
        return config

    # Get 'vpp settings' config
    config['vpp_settings'] = conf.get_config_dict(
        ['vpp', 'settings'],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    # NAT dependency
    if conf.exists(['vpp', 'nat', 'nat44']):
        set_dependents('vpp_nat_nat44', conf)
    if conf.exists(['vpp', 'nat', 'cgnat']):
        set_dependents('vpp_nat_cgnat', conf)

    # ACL dependency
    if conf.exists(['vpp', 'acl']):
        set_dependents('vpp_acl', conf)

    return config


def verify(config):
    # No need to verify anything if vpp is removed
    if 'remove_vpp' in config:
        return None

    if not is_systemd_service_active('vpp.service'):
        raise ConfigError(
            'Cannot configure VPP loopback interface: vpp.service is not running'
        )


def generate(config):
    pass


def apply(config):
    if 'remove_vpp' in config:
        return None

    ifname = config.get('ifname')
    loopback = VPPLoopbackInterface(ifname, config)
    loopback.remove()

    if 'deleted' in config:
        return

    loopback.update(config)

    call_dependents()

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
