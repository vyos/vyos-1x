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
from vyos.utils.process import call
from vyos.zerotier import ZEROTIER_HOME
from vyos.zerotier import ZEROTIER_UNIT
from vyos.zerotier import local_conf
from vyos.zerotier import write_identity
from vyos.zerotier import write_json

airbag.enable()

interface_base = ['interfaces', 'zerotier']


def _has_active_interfaces(conf):
    if not conf.exists(interface_base):
        return False

    interfaces = conf.get_config_dict(interface_base, key_mangling=('-', '_'),
                                      no_tag_node_value_mangle=True,
                                      get_first_key=True,
                                      with_recursive_defaults=True)
    for config in interfaces.values():
        if 'disable' not in config and 'network_id' in config:
            return True

    return False


def get_config(config=None):
    conf = config or Config()
    base = ['service', 'zerotier']

    if not conf.exists(base):
        return None

    zerotier = conf.get_config_dict(base, key_mangling=('-', '_'),
                                    get_first_key=True,
                                    with_recursive_defaults=True)
    zerotier['has_active_interfaces'] = _has_active_interfaces(conf)

    return zerotier


def verify(zerotier):
    if not zerotier:
        return None

    if 'identity' not in zerotier or 'secret' not in zerotier['identity']:
        raise ConfigError('ZeroTier identity secret is required')

    multicore = zerotier.get('multicore', {})
    if ('core_count' in multicore or 'cpu_pinning' in multicore) and 'enable' not in multicore:
        raise ConfigError('ZeroTier multicore must be enabled when core-count or cpu-pinning is configured')

    if 'disable_secondary_port' in zerotier and zerotier.get('port', {}).get('secondary'):
        raise ConfigError('ZeroTier secondary port cannot be configured when disable-secondary-port is set')

    for moon, config in zerotier.get('moon', {}).items():
        if 'seed' not in config:
            raise ConfigError(f'ZeroTier moon "{moon}" requires a seed')

    return None


def generate(zerotier):
    if not zerotier:
        return None

    ZEROTIER_HOME.mkdir(parents=True, exist_ok=True)
    (ZEROTIER_HOME / 'moons.d').mkdir(parents=True, exist_ok=True)
    networks_dir = ZEROTIER_HOME / 'networks.d'
    if networks_dir.exists():
        for path in networks_dir.glob('*.conf'):
            path.unlink()

    write_identity(zerotier['identity']['secret'])
    write_json(ZEROTIER_HOME / 'local.conf', local_conf(zerotier))

    return None


def apply(zerotier):
    if not zerotier:
        call(f'systemctl --quiet stop {ZEROTIER_UNIT}')
        call(f'systemctl --quiet disable {ZEROTIER_UNIT}')
        return None

    if not zerotier.get('has_active_interfaces'):
        call(f'systemctl --quiet stop {ZEROTIER_UNIT}')
        call(f'systemctl --quiet disable {ZEROTIER_UNIT}')
        return None

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
