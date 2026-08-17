#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.

# pylint: disable=no-member

import fcntl
import os
import struct
from sys import exit

from pyroute2.iproute import IPRoute

from vyos import ConfigError
from vyos import airbag
from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_bond_bridge_member
from vyos.configverify import verify_mirror_redirect
from vyos.configverify import verify_vrf
from vyos.ifconfig import ZeroTierIf
from vyos.utils.process import call
from vyos.zerotier import ZEROTIER_HOME
from vyos.zerotier import ZEROTIER_UNIT
from vyos.zerotier import ZEROTIER_GROUP
from vyos.zerotier import ZEROTIER_USER
from vyos.zerotier import local_conf
from vyos.zerotier import write_identity
from vyos.zerotier import write_json
from vyos.utils.permission import chown

airbag.enable()

base = ['interfaces', 'zerotier']
TUNSETIFF = 0x400454ca
TUNSETPERSIST = 0x400454cb
IFF_TAP = 0x0002
IFF_NO_PI = 0x1000


def _all_interfaces(conf):
    if not conf.exists(base):
        return {}

    return conf.get_config_dict(base, key_mangling=('-', '_'),
                                no_tag_node_value_mangle=True,
                                get_first_key=True,
                                with_recursive_defaults=True)


def get_config(config=None):
    conf = config or Config()
    ifname, zerotier = get_interface_dict(conf, base)
    zerotier['interfaces'] = _all_interfaces(conf)

    if conf.exists(['service', 'zerotier']):
        zerotier['service'] = conf.get_config_dict(['service', 'zerotier'],
                                                   key_mangling=('-', '_'),
                                                   get_first_key=True,
                                                   with_recursive_defaults=True)
    return zerotier


def verify(zerotier):
    if 'deleted' in zerotier:
        verify_bridge_delete(zerotier)
        return None

    if 'disable' in zerotier:
        return None

    if 'network_id' not in zerotier:
        raise ConfigError('ZeroTier network-id is required')

    service = zerotier.get('service', {})
    if 'identity' not in service or 'secret' not in service.get('identity', {}):
        raise ConfigError('service zerotier identity secret is required when ZeroTier interfaces are configured')

    seen = {}
    for ifname, config in zerotier.get('interfaces', {}).items():
        if 'disable' in config or 'network_id' not in config:
            continue
        nwid = config['network_id'].lower()
        if nwid in seen and seen[nwid] != ifname:
            raise ConfigError(f'ZeroTier network-id {nwid} is already used by interface {seen[nwid]}')
        seen[nwid] = ifname

    verify_address(zerotier)
    verify_vrf(zerotier)
    verify_bond_bridge_member(zerotier)
    verify_mirror_redirect(zerotier)

    return None


def _active_networks(zerotier):
    active = {}
    for ifname, config in zerotier.get('interfaces', {}).items():
        if 'disable' in config or 'network_id' not in config:
            continue
        active[config['network_id'].lower()] = ifname
    return active


def _has_active_interfaces(zerotier):
    return bool(_active_networks(zerotier))


def _set_addrgenmode_none(ifname):
    with IPRoute() as ipr:
        indexes = ipr.link_lookup(ifname=ifname)
        if indexes:
            ipr.link('set', index=indexes[0], addrgenmode='none')


def _create_persistent_tap(ifname):
    if ZeroTierIf.exists(ifname):
        _set_addrgenmode_none(ifname)
        return None

    fd = os.open('/dev/net/tun', os.O_RDWR | os.O_NONBLOCK)
    ifreq = struct.pack('16sH', ifname.encode()[:15].ljust(16, b'\0'), IFF_TAP | IFF_NO_PI)
    try:
        fcntl.ioctl(fd, TUNSETIFF, ifreq)
        _set_addrgenmode_none(ifname)
        fcntl.ioctl(fd, TUNSETPERSIST, 1)
    finally:
        os.close(fd)

    return None


def _delete_tap(ifname):
    if ZeroTierIf.exists(ifname):
        zt = ZeroTierIf(ifname, create=False)
        zt.remove()


def generate(zerotier):
    ZEROTIER_HOME.mkdir(parents=True, exist_ok=True)
    (ZEROTIER_HOME / 'moons.d').mkdir(parents=True, exist_ok=True)
    chown(ZEROTIER_HOME, ZEROTIER_USER, ZEROTIER_GROUP)
    chown(ZEROTIER_HOME / 'moons.d', ZEROTIER_USER, ZEROTIER_GROUP)

    service = zerotier.get('service', {})
    if service:
        if service.get('identity', {}).get('secret'):
            write_identity(service['identity']['secret'])
        write_json(ZEROTIER_HOME / 'local.conf', local_conf(service))

    for stale_file in ('devicemap', 'interfaces.json'):
        try:
            (ZEROTIER_HOME / stale_file).unlink()
        except FileNotFoundError:
            pass
    networks_dir = ZEROTIER_HOME / 'networks.d'
    if networks_dir.exists():
        for path in networks_dir.glob('*.conf'):
            path.unlink()

    return None


def apply(zerotier):
    ifname = zerotier['ifname']
    has_active_interfaces = _has_active_interfaces(zerotier)

    if 'deleted' in zerotier or 'disable' in zerotier:
        if not has_active_interfaces:
            call(f'systemctl --quiet stop {ZEROTIER_UNIT}')
            call(f'systemctl --quiet disable {ZEROTIER_UNIT}')
        _delete_tap(ifname)
        return None

    _create_persistent_tap(ifname)
    zt = ZeroTierIf(ifname, create=False)
    zt.update(zerotier)

    call(f'systemctl --quiet disable {ZEROTIER_UNIT}')
    call(f'systemctl --quiet start {ZEROTIER_UNIT}')

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
