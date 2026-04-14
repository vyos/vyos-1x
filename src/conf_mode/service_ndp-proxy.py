#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
import json

from sys import exit
from pathlib import Path

from vyos.config import Config
from vyos.configverify import verify_interface_exists
from vyos.utils.process import call
from vyos.template import render
from vyos import ConfigError
from vyos import airbag
airbag.enable()

systemd_service = 'ndppd.service'
ndppd_config = '/run/ndppd/ndppd.conf'
route_sync_systemd_service = 'vyos-ndp-route-sync.service'
route_sync_config = Path('/run/ndppd/route-sync.conf')
route_sync_proto = Path('/etc/iproute2/rt_protos.d/ndp_proxy_sync.conf')
route_sync_proto_name = 'ndp-proxy-sync'
route_sync_proto_id = 190
route_sync_helper = '/usr/libexec/vyos/vyos-ndp-route-sync.py'
route_sync_hold_time = 120

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'ndp-proxy']
    if not conf.exists(base):
        return None

    ndpp = conf.get_config_dict(base, key_mangling=('-', '_'),
                                get_first_key=True,
                                with_recursive_defaults=True)

    return ndpp

def verify(ndpp):
    if not ndpp:
        return None

    if 'interface' not in ndpp:
        return None

    for interface, interface_config in ndpp['interface'].items():
        if 'disable' in interface_config:
            continue

        verify_interface_exists(ndpp, interface)

        if 'prefix' not in interface_config:
            continue

        for prefix, prefix_config in interface_config['prefix'].items():
            if 'disable' in prefix_config:
                continue

            mode = prefix_config.get('mode')
            prefix_interface = prefix_config.get('interface')
            route_sync = 'route_sync' in prefix_config

            if mode == 'interface':
                if not prefix_interface:
                    raise ConfigError(f'Prefix "{prefix}" uses interface mode but no interface defined!')
                verify_interface_exists(ndpp, prefix_interface)
                continue

            if prefix_interface:
                raise ConfigError(f'Prefix "{prefix}" does not use interface mode, thus interface can not be defined!')

            if route_sync:
                raise ConfigError(f'Prefix "{prefix}" route-sync requires interface mode!')

    return None

def get_route_sync_config(ndpp):
    if not ndpp or 'interface' not in ndpp:
        return None

    rules = []
    for _, interface_config in ndpp['interface'].items():
        if 'disable' in interface_config or 'prefix' not in interface_config:
            continue

        for prefix, prefix_config in interface_config['prefix'].items():
            if 'disable' in prefix_config or 'route_sync' not in prefix_config:
                continue

            rules.append({
                'prefix': prefix,
                'interface': prefix_config.get('interface'),
            })

    if not rules:
        return None

    return {
        'proto': route_sync_proto_name,
        'interval': 2,
        'hold_time': route_sync_hold_time,
        'rules': rules,
    }

def generate(ndpp):
    if not ndpp:
        route_sync_config.unlink(missing_ok=True)
        return None

    render(ndppd_config, 'ndppd/ndppd.conf.j2', ndpp)

    route_sync = get_route_sync_config(ndpp)
    if route_sync:
        route_sync_proto.parent.mkdir(parents=True, exist_ok=True)
        route_sync_proto.write_text(f'{route_sync_proto_id}  {route_sync_proto_name}\n')
        route_sync_config.parent.mkdir(parents=True, exist_ok=True)
        route_sync_config.write_text(json.dumps(route_sync, indent=4))
    else:
        route_sync_config.unlink(missing_ok=True)

    return None

def apply(ndpp):
    if not ndpp:
        call(f'systemctl stop {systemd_service}')
        call(f'systemctl stop {route_sync_systemd_service}')
        call(f'/usr/bin/python3 {route_sync_helper} --cleanup')
        if os.path.isfile(ndppd_config):
            os.unlink(ndppd_config)
        route_sync_config.unlink(missing_ok=True)
        return None

    call(f'systemctl reload-or-restart {systemd_service}')
    if get_route_sync_config(ndpp):
        call(f'systemctl restart {route_sync_systemd_service}')
    else:
        call(f'systemctl stop {route_sync_systemd_service}')
        call(f'/usr/bin/python3 {route_sync_helper} --cleanup')
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
