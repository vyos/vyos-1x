#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.

from sys import exit

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
from vyos.zerotier import ZeroTierAPIError
from vyos.zerotier import ZEROTIER_HOME
from vyos.zerotier import ZEROTIER_UNIT
from vyos.zerotier import wait_for_api
from vyos.zerotier import api_request

airbag.enable()

base = ['interfaces', 'zerotier']


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

    address = zerotier.get('address', [])
    if address and 'allow_managed' in zerotier:
        raise ConfigError('ZeroTier allow-managed cannot be used together with manual interface addresses')

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


def _network_settings(config):
    manual_address = bool(config.get('address', []))
    return {
        'allowManaged': not manual_address,
        'allowGlobal': 'allow_global' in config,
        'allowDefault': 'allow_default_route' in config,
        'allowDNS': False,
    }


def generate(zerotier):
    networks_dir = ZEROTIER_HOME / 'networks.d'
    networks_dir.mkdir(parents=True, exist_ok=True)

    active = {}
    for ifname, config in zerotier.get('interfaces', {}).items():
        if 'disable' in config or 'network_id' not in config:
            continue
        active[config['network_id'].lower()] = ifname

    devicemap = ''.join(f'{network}={ifname}\n' for network, ifname in sorted(active.items()))
    (ZEROTIER_HOME / 'devicemap').write_text(devicemap)

    for network, ifname in active.items():
        config = zerotier['interfaces'][ifname]
        (networks_dir / f'{network}.conf').touch(exist_ok=True)
        settings = _network_settings(config)
        (networks_dir / f'{network}.local.conf').write_text(
            ''.join(f'{key}={int(value) if isinstance(value, bool) else value}\n'
                    for key, value in settings.items()))

    return None


def apply(zerotier):
    ifname = zerotier['ifname']

    if 'deleted' in zerotier or 'disable' in zerotier:
        if 'network_id' in zerotier and wait_for_api(timeout=3):
            try:
                api_request('DELETE', f'/network/{zerotier["network_id"].lower()}')
            except ZeroTierAPIError:
                pass
        if ZeroTierIf.exists(ifname):
            zt = ZeroTierIf(ifname, create=False)
            zt.remove()
        return None

    zt = ZeroTierIf(**zerotier)
    zt.update(zerotier)

    call(f'systemctl --quiet start {ZEROTIER_UNIT}')
    if wait_for_api():
        network = zerotier['network_id'].lower()
        api_request('POST', f'/network/{network}', _network_settings(zerotier))

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
