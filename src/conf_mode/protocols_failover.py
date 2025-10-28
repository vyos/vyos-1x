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

import json
import os

from pathlib import Path
from sys import argv

from vyos.config import Config
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.process import is_systemd_service_running
from vyos import ConfigError
from vyos import airbag

airbag.enable()


service_name = 'vyos-failover'
service_conf_dir = Path(f'/run/{service_name}.conf.d/')
systemd_service = '/run/systemd/system/vyos-failover.service'
rt_proto_failover = Path('/etc/iproute2/rt_protos.d/failover.conf')


def get_vrf_name():
    if argv and len(argv) > 1:
        return argv[1]
    return None


def get_service_conf_path():
    vrf_name = get_vrf_name()
    if vrf_name:
        filename = f'vrf-{vrf_name}.conf'
    else:
        filename = 'default.conf'
    return service_conf_dir / filename


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    vrf_name = get_vrf_name()
    if vrf_name:
        base = ['vrf', 'name', vrf_name]
    else:
        base = []

    base += ['protocols', 'failover']

    failover = conf.get_config_dict(base, key_mangling=('-', '_'),
                                    get_first_key=True)

    # Set default values only if we set config
    if failover.get('route') is not None:
        failover = conf.merge_defaults(failover, recursive=True)

    if failover:
        failover['vrf_context'] = vrf_name

    return failover

def verify(failover):
    # bail out early - looks like removal from running config
    if not failover:
        return None

    if 'route' not in failover:
        raise ConfigError(f'Failover "route" is mandatory!')

    def _verify_route_item(item_config, item_description, interface_mandatory):
        if interface_mandatory and 'interface' not in item_config:
            raise ConfigError(
                f'Interface for route "{route}" {item_description} is mandatory!'
            )

        if not item_config.get('check'):
            raise ConfigError(f'Check target for {item_description} is mandatory!')

        if 'target' not in item_config['check']:
            raise ConfigError(f'Check target for {item_description} is mandatory!')

        check_type = item_config['check']['type']
        if check_type == 'tcp' and 'port' not in item_config['check']:
            raise ConfigError(
                f'Check port for {item_description} and type TCP is mandatory!'
            )

        errors = {
            'icmp': {},
            'tcp': {
                'interface': 'Check target "interface" option does nothing for type TCP. Use "vrf" if needed',
            },
            'arp': {
                'vrf': 'Check target "vrf" option is incompatible with type ARP, use "interface" option if needed',
            },
        }

        for target, target_config in item_config['check']['target'].items():
            for key, msg in errors[check_type].items():
                if key in target_config:
                    raise ConfigError(msg)

    for route, route_config in failover['route'].items():
        if not route_config.get('next_hop') and not route_config.get('dhcp_interface'):
            raise ConfigError(
                f'Either next-hop or dhcp-interface for "{route}" is mandatory!'
            )

        if route_config.get('next_hop'):
            for next_hop, next_hop_config in route_config.get('next_hop').items():
                _verify_route_item(
                    next_hop_config, f'next-hop "{next_hop}"', interface_mandatory=True
                )

        if route_config.get('dhcp_interface'):
            for dhcp_interface, dhcp_interface_config in route_config.get(
                'dhcp_interface'
            ).items():
                _verify_route_item(
                    dhcp_interface_config,
                    f'dhcp-interface "{dhcp_interface}"',
                    interface_mandatory=False,
                )

    return None


def generate(failover):
    service_conf = get_service_conf_path()
    if not failover:
        service_conf.unlink(missing_ok=True)
        try:
            os.rmdir(service_conf_dir)
        # Ignore if directory doesn't exist
        # or not empty (probably configs for other VRFs are there)
        except (FileNotFoundError, OSError):
            pass
        return None

    # Add own rt_proto 'failover'
    # Helps to detect all own routes 'proto failover'
    rt_proto_failover.write_text('111  failover\n')

    service_conf_dir.mkdir(exist_ok=True)

    # Write configuration file
    conf_json = json.dumps(failover, indent=4)
    service_conf.write_text(conf_json)
    render(
        systemd_service,
        'protocols/systemd_vyos_failover_service.j2',
        {'config_dir': str(service_conf_dir)},
    )

    return None

def apply(failover):
    # If directory is removed - we can stop the service
    if not service_conf_dir.is_dir():
        call(f'systemctl stop {service_name}.service')
        call('systemctl daemon-reload')
    # Otherwise even if `failover` is False, service is
    # still needed for other VRFs.
    else:
        # Daemon watches for configuration updates, so we need only
        # to start it if it is not started yet
        if not is_systemd_service_running(service_name):
            call('systemctl daemon-reload')
            call(f'systemctl start {service_name}.service')

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
