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
from vyos.template import render
from vyos.utils.process import call
from vyos.zerotier import ZEROTIER_HOME
from vyos.zerotier import ZEROTIER_UNIT
from vyos.zerotier import local_conf
from vyos.zerotier import wait_for_api
from vyos.zerotier import api_request
from vyos.zerotier import write_identity
from vyos.zerotier import write_json

airbag.enable()

unit_file = '/run/systemd/system/vyos-zerotier.service'


def get_config(config=None):
    conf = config or Config()
    base = ['service', 'zerotier']

    if not conf.exists(base):
        return None

    return conf.get_config_dict(base, key_mangling=('-', '_'),
                                get_first_key=True,
                                with_recursive_defaults=True)


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
    (ZEROTIER_HOME / 'networks.d').mkdir(parents=True, exist_ok=True)
    (ZEROTIER_HOME / 'moons.d').mkdir(parents=True, exist_ok=True)

    write_identity(zerotier['identity']['secret'])
    write_json(ZEROTIER_HOME / 'local.conf', local_conf(zerotier))
    render(unit_file, 'zerotier/systemd-unit.j2', {'zerotier_home': ZEROTIER_HOME})

    return None


def apply(zerotier):
    if not zerotier:
        call(f'systemctl --quiet stop {ZEROTIER_UNIT}')
        call(f'systemctl --quiet disable {ZEROTIER_UNIT}')
        return None

    call('systemctl daemon-reload')
    call(f'systemctl --quiet enable {ZEROTIER_UNIT}')
    call(f'systemctl --quiet restart {ZEROTIER_UNIT}')

    if wait_for_api():
        for moon, config in zerotier.get('moon', {}).items():
            api_request('POST', f'/moon/{moon}', {'seed': config['seed']})

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
