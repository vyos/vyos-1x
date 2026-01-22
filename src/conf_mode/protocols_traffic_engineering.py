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

from sys import exit

from vyos.config import Config
from vyos.configverify import has_frr_protocol_in_dict
from vyos.frrender import FRRender
from vyos.frrender import get_frrender_dict
from vyos.utils.process import is_systemd_service_running
from vyos import ConfigError
from vyos import airbag

airbag.enable()


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    return get_frrender_dict(conf)


def verify(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'traffic_engineering'):
        return None

    te = config_dict['traffic_engineering']

    group_by_bit_position = {}
    if 'admin_group' in te:
        for admin_group, admin_group_data in te['admin_group'].items():
            if 'bit_position' not in admin_group_data:
                raise ConfigError(
                    f'Missing required "bit-position" in group {admin_group}'
                )
            if admin_group_data['bit_position'] in group_by_bit_position:
                other = group_by_bit_position[admin_group_data['bit_position']]
                raise ConfigError(
                    f'Two admin-groups cannot have same bit positions! Conflicting groups: {admin_group} and {other}'
                )
            group_by_bit_position[admin_group_data['bit_position']] = admin_group

    all_groups = group_by_bit_position.values()

    if 'interface' in te:
        for interface, interface_data in te['interface'].items():
            if 'admin_group' not in interface_data:
                continue
            for grp in interface_data['admin_group']:
                if grp not in all_groups:
                    raise ConfigError(
                        f'Unknown admin-group "{grp}" set for interface "{interface}"'
                    )

    return None


def generate(config_dict):
    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().generate(config_dict)
    return None


def apply(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'traffic_engineering'):
        return None

    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().apply()
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
