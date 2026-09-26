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

from sys import exit

from vyos.config import Config
from vyos.configdict import get_accel_dict
from vyos.configverify import verify_interface_exists
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.dict import dict_search
from vyos.accel_ppp_util import get_pools_in_order
from vyos.accel_ppp_util import verify_accel_ppp_name_servers
from vyos.accel_ppp_util import verify_accel_ppp_wins_servers
from vyos.accel_ppp_util import verify_accel_ppp_ip_pool
from vyos.accel_ppp_util import verify_accel_ppp_authentication
from vyos.vpp.utils import cli_ifaces_list
from vyos.base import Warning
from vyos import ConfigError
from vyos import airbag

airbag.enable()


ipoe_conf = '/run/accel-pppd/ipoe.conf'
ipoe_chap_secrets = '/run/accel-pppd/ipoe.chap-secrets'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'ipoe-server']
    if not conf.exists(base):
        return None

    # retrieve common dictionary keys
    ipoe = get_accel_dict(conf, base, ipoe_chap_secrets)

    if dict_search('client_ip_pool', ipoe):
        # Multiple named pools require ordered values T5099
        ipoe['ordered_named_pools'] = get_pools_in_order(
            dict_search('client_ip_pool', ipoe)
        )

    ipoe['server_type'] = 'ipoe'

    ipoe['vpp_ifaces'] = cli_ifaces_list(conf)

    return ipoe


def verify(ipoe):
    if not ipoe:
        return None

    if 'interface' not in ipoe:
        raise ConfigError('No IPoE interface configured')

    for interface, iface_config in ipoe['interface'].items():
        if ipoe.get('vpp_ifaces'):
            base_interface = interface.split('.')[0]
            if base_interface in ipoe['vpp_ifaces']:
                raise ConfigError(
                    f'{interface} is a VPP interface and cannot be used for IPoE!'
                )

        verify_interface_exists(ipoe, interface, warning_only=True)
        if 'client_subnet' in iface_config and 'vlan' in iface_config:
            raise ConfigError(
                'Options "client-subnet" and "vlan" are mutually exclusive, '
                'use "client-ip-pool" instead!'
            )
        if 'vlan_mon' in iface_config and 'vlan' not in iface_config:
            raise ConfigError('Option "vlan-mon" requires "vlan" to be set!')

        if 'lua_username' in iface_config:
            if 'lua_file' not in ipoe:
                raise ConfigError(
                    'Option "lua-username" requires "lua-file" to be set!'
                )
            if dict_search('authentication.mode', ipoe) != 'radius':
                raise ConfigError(
                    'Can configure username with Lua script only for RADIUS authentication'
                )

        if dict_search('external_dhcp.dhcp_relay', iface_config):
            if not dict_search('external_dhcp.giaddr', iface_config):
                raise ConfigError(
                    f'"external-dhcp dhcp-relay" requires "giaddr" to be set for interface {interface}'
                )

    verify_accel_ppp_authentication(ipoe, local_users=False)
    verify_accel_ppp_ip_pool(ipoe)
    verify_accel_ppp_name_servers(ipoe)
    verify_accel_ppp_wins_servers(ipoe)

    # accel-ppp never rejects inconsistent DHCP lease timings, it silently
    # recalculates them - and it does so against its own defaults for every
    # option left unset, so a configured value can be overridden even when
    # nothing it is compared against appears in our configuration. Mirror
    # that calculation from accel-ppp's ipoe.c:load_config() and report the
    # values that will not survive it.
    lease_time = int(dict_search('lease_time', ipoe) or 600)
    max_lease_time = dict_search('max_lease_time', ipoe)
    renew_time = dict_search('renew_time', ipoe)
    rebind_time = dict_search('rebind_time', ipoe)

    # An unset or too large "renew-time" becomes half the lease time, an unset
    # or too large "rebind-time" seven eighths of it (integer division, term by
    # term, as accel-ppp computes it).
    if renew_time and int(renew_time) <= lease_time:
        effective_renew_time = int(renew_time)
    else:
        effective_renew_time = lease_time // 2

    if rebind_time and int(rebind_time) <= lease_time:
        effective_rebind_time = int(rebind_time)
    else:
        effective_rebind_time = lease_time // 2 + lease_time // 4 + lease_time // 8

    # T1 must stay below T2, so accel-ppp pulls "renew-time" back to 4/7 of the
    # rebind time - the step that overrides an otherwise valid "renew-time".
    if effective_rebind_time and effective_renew_time > effective_rebind_time:
        effective_renew_time = effective_rebind_time * 4 // 7

    if max_lease_time and int(max_lease_time) < lease_time:
        Warning(
            f'"max-lease-time" ({max_lease_time}) is lower than "lease-time" '
            f'({lease_time}) and will have no effect'
        )

    if renew_time and int(renew_time) != effective_renew_time:
        Warning(
            f'"renew-time" ({renew_time}) will be overridden by accel-ppp with '
            f'{effective_renew_time}, derived from "lease-time" {lease_time} '
            f'and "rebind-time" {effective_rebind_time}'
        )

    if rebind_time and int(rebind_time) != effective_rebind_time:
        Warning(
            f'"rebind-time" ({rebind_time}) will be overridden by accel-ppp '
            f'with {effective_rebind_time}, derived from "lease-time" '
            f'{lease_time}'
        )

    return None


def generate(ipoe):
    if not ipoe:
        return None

    render(ipoe_conf, 'accel-ppp/ipoe.config.j2', ipoe)

    if dict_search('authentication.mode', ipoe) == 'local':
        render(
            ipoe_chap_secrets, 'accel-ppp/chap-secrets.ipoe.j2', ipoe, permission=0o640
        )
    return None


def apply(ipoe):
    systemd_service = 'accel-ppp@ipoe.service'
    if ipoe is None:
        call(f'systemctl stop {systemd_service}')
        for file in [ipoe_conf, ipoe_chap_secrets]:
            if os.path.exists(file):
                os.unlink(file)

        return None

    # Accel-pppd does not do soft-reload correctly.
    # Most of the changes require restarting the service
    call(f'systemctl restart {systemd_service}')


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
