#!/usr/bin/env python3
#
# Copyright (C) 2018-2024 VyOS maintainers and contributors
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

from vyos.config import Config
from vyos.config import config_dict_merge
from vyos.configdict import is_node_changed
from vyos.configverify import verify_vrf
from vyos.configverify import verify_interface_exists
from vyos.utils.process import call
from vyos.utils.permission import chmod_750
from vyos.utils.network import get_interface_config
from vyos.template import render
from vyos.template import is_ipv4
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = r'/run/chrony/chrony.conf'
systemd_override = r'/run/systemd/system/chrony.service.d/override.conf'
user_group = '_chrony'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'ntp']
    if not conf.exists(base):
        return None

    ntp = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    ntp['config_file'] = config_file
    ntp['user'] = user_group

    tmp = is_node_changed(conf, base + ['vrf'])
    if tmp: ntp.update({'restart_required': {}})

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = conf.get_config_defaults(**ntp.kwargs, recursive=True)
    # Only defined PTP default port, if PTP feature is in use
    if 'ptp' not in ntp:
        del default_values['ptp']

    ntp = config_dict_merge(default_values, ntp)
    return ntp

def verify(ntp):
    # bail out early - looks like removal from running config
    if not ntp:
        return None

    if 'server' not in ntp:
        raise ConfigError('NTP server not configured')

    verify_vrf(ntp)

    if 'interface' in ntp:
        # If ntpd should listen on a given interface, ensure it exists
        interface = ntp['interface']
        verify_interface_exists(ntp, interface)

        # If we run in a VRF, our interface must belong to this VRF, too
        if 'vrf' in ntp:
            tmp = get_interface_config(interface)
            vrf_name = ntp['vrf']
            if 'master' not in tmp or tmp['master'] != vrf_name:
                raise ConfigError(f'NTP runs in VRF "{vrf_name}" - "{interface}" '\
                                  f'does not belong to this VRF!')

    if 'listen_address' in ntp:
        ipv4_addresses = 0
        ipv6_addresses = 0
        for address in ntp['listen_address']:
            if is_ipv4(address):
                ipv4_addresses += 1
            else:
                ipv6_addresses += 1
        if ipv4_addresses > 1:
            raise ConfigError(f'NTP Only admits one ipv4 value for listen-address parameter ')
        if ipv6_addresses > 1:
            raise ConfigError(f'NTP Only admits one ipv6 value for listen-address parameter ')

    if 'server' in ntp:
        for host, server in ntp['server'].items():
            if 'ptp' in server:
                if 'ptp' not in ntp:
                    raise ConfigError('PTP must be enabled for the NTP service '\
                                      f'before it can be used for server "{host}"')
                else:
                    break

    return None

def generate(ntp):
    # bail out early - looks like removal from running config
    if not ntp:
        return None

    render(config_file, 'chrony/chrony.conf.j2', ntp, user=user_group, group=user_group)
    render(systemd_override, 'chrony/override.conf.j2', ntp, user=user_group, group=user_group)

    # Ensure proper permission for chrony command socket
    config_dir = os.path.dirname(config_file)
    chmod_750(config_dir)

    return None

def apply(ntp):
    systemd_service = 'chrony.service'
    # Reload systemd manager configuration
    call('systemctl daemon-reload')

    if not ntp:
        # NTP support is removed in the commit
        call(f'systemctl stop {systemd_service}')
        if os.path.exists(config_file):
            os.unlink(config_file)
        if os.path.isfile(systemd_override):
            os.unlink(systemd_override)
        return

    # we need to restart the service if e.g. the VRF name changed
    systemd_action = 'reload-or-restart'
    if 'restart_required' in ntp:
        systemd_action = 'restart'

    call(f'systemctl {systemd_action} {systemd_service}')
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
