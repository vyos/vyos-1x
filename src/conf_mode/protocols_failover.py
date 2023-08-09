#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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

import json

from pathlib import Path

from vyos.config import Config
from vyos.template import render
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag

airbag.enable()


service_name = 'vyos-failover'
service_conf = Path(f'/run/{service_name}.conf')
systemd_service = '/run/systemd/system/vyos-failover.service'
rt_proto_failover = '/etc/iproute2/rt_protos.d/failover.conf'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['protocols', 'failover']
    failover = conf.get_config_dict(base, key_mangling=('-', '_'),
                                    get_first_key=True)

    # Set default values only if we set config
    if failover.get('route') is not None:
        failover = conf.merge_defaults(failover, recursive=True)

    return failover

def verify(failover):
    # bail out early - looks like removal from running config
    if not failover:
        return None

    if 'route' not in failover:
        raise ConfigError(f'Failover "route" is mandatory!')

    for route, route_config in failover['route'].items():
        if not route_config.get('next_hop'):
            raise ConfigError(f'Next-hop for "{route}" is mandatory!')

        for next_hop, next_hop_config in route_config.get('next_hop').items():
            if 'interface' not in next_hop_config:
                raise ConfigError(f'Interface for route "{route}" next-hop "{next_hop}" is mandatory!')

            if not next_hop_config.get('check'):
                raise ConfigError(f'Check target for next-hop "{next_hop}" is mandatory!')

            if 'target' not in next_hop_config['check']:
                raise ConfigError(f'Check target for next-hop "{next_hop}" is mandatory!')

            check_type = next_hop_config['check']['type']
            if check_type == 'tcp' and 'port' not in next_hop_config['check']:
                raise ConfigError(f'Check port for next-hop "{next_hop}" and type TCP is mandatory!')

    return None

def generate(failover):
    if not failover:
        service_conf.unlink(missing_ok=True)
        return None

    # Add own rt_proto 'failover'
    # Helps to detect all own routes 'proto failover'
    with open(rt_proto_failover, 'w') as f:
        f.write('111  failover\n')

    # Write configuration file
    conf_json = json.dumps(failover, indent=4)
    service_conf.write_text(conf_json)
    render(systemd_service, 'protocols/systemd_vyos_failover_service.j2', failover)

    return None

def apply(failover):
    if not failover:
        call(f'systemctl stop {service_name}.service')
        call('ip route flush protocol failover')
    else:
        call('systemctl daemon-reload')
        call(f'systemctl restart {service_name}.service')
        call(f'ip route flush protocol failover')

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
