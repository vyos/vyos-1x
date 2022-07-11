#!/usr/bin/env python3
#
# Copyright (C) 2019-2022 VyOS maintainers and contributors
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
import shutil
from ipaddress import ip_address, ip_network
from sys import exit

from vyos import ConfigError, airbag
from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configverify import (verify_mirror_redirect, verify_vrf)
from vyos.ifconfig import NAT64If
from vyos.template import render
from vyos.util import call, dict_search

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
    base = ['interfaces', 'nat64']
    _, nat64 = get_interface_dict(conf, base)
    return nat64


def verify(nat64):
    if 'deleted' in nat64:
        # bail out early
        return None

    ifname = nat64['ifname']
    # verify MTU
    # configverify.verify_mtu_ipv6 can't be used here
    # because the tayga tun interface may not have an IPv6 address.
    if 'mtu' in nat64:
        # IPv6 minimum required link mtu
        min_mtu = 1280
        if int(nat64['mtu']) < min_mtu:
            error_msg = f'IPv6 forwarding will be configured on interface "{ifname}",\n' \
                        f'the required minimum MTU is {min_mtu}!'
            raise ConfigError(error_msg)
    verify_vrf(nat64)
    verify_mirror_redirect(nat64)

    if "ipv4_address" not in nat64:
        raise ConfigError('ipv4-address is required for NAT64 translator.')
    ipv4_address = ip_address(nat64["ipv4_address"])
    prefix = dict_search("stateful.prefix", nat64)
    host_mapping = dict_search("host_mapping.ipv6", nat64)
    if not host_mapping and not prefix:
        raise ConfigError(
            "A NAT64 prefix is required if no host mappings are defined.")
    if prefix:
        prefix = ip_network(prefix)
        if prefix.prefixlen not in [32, 40, 48, 56, 64, 96]:
            raise ConfigError(
                "NAT64 prefix length must be one of 32, 40, 48, 56, 64 or 96.")
    if host_mapping:
        for ipv6, config in host_mapping.items():
            if "ipv4" not in config:
                raise ConfigError(
                    f"A mapped IPv4 address is required for IPv6 host {ipv6}")
            if prefix and ip_address(ipv6) in prefix:
                raise ConfigError(
                    f"IPv6 host address {ipv6} cannot overlap with NAT64 prefix {prefix}")

    if "ipv6_address" not in nat64:
        if not prefix:
            raise ConfigError(
                'ipv6-address is required for NAT64 translator unless a dynamic prefix is specified.')
        if prefix == ip_network("64:ff9b::/96") and ipv4_address.is_private:
            raise ConfigError(
                'ipv6-address is required for NAT64 translator when well-known prefix 64:ff9b::/96 and private IPv4 address is used.')
    return None


def generate(nat64):
    if 'deleted' in nat64 or 'disable' in nat64:
        return None
    ifname = nat64['ifname']
    config_file = f'/run/tayga/{ifname}.conf'
    render(config_file, 'tayga/tayga.conf.j2', nat64)
    return None


def apply(nat64):
    ifname = nat64['ifname']
    d = NAT64If(ifname)
    if 'deleted' in nat64 or 'disable' in nat64:
        call(f'systemctl stop tayga@{ifname}.service')
        if 'deleted' in nat64:
            d.remove()
            config_file = f'/run/tayga/{ifname}.conf'
            if os.path.isfile(config_file):
                os.unlink(config_file)
            configd = f'/run/tayga/{ifname}.d'
            shutil.rmtree(configd, ignore_errors=True)
        return None

    call(f'systemctl restart tayga@{ifname}.service')
    d.update(nat64)
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
