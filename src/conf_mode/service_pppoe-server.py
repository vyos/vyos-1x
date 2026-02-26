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
from vyos.configdict import is_node_changed, node_changed
from vyos.configdiff import Diff
from vyos.configverify import verify_interface_exists
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.process import is_systemd_service_active
from vyos.utils.dict import dict_search
from vyos.accel_ppp_util import verify_accel_ppp_name_servers
from vyos.accel_ppp_util import verify_accel_ppp_wins_servers
from vyos.accel_ppp_util import verify_accel_ppp_authentication
from vyos.accel_ppp_util import verify_accel_ppp_ip_pool
from vyos.accel_ppp_util import get_pools_in_order
from vyos import ConfigError
from vyos import airbag
from vyos.vpp.control_vpp import VPPControl

airbag.enable()

pppoe_conf = r'/run/accel-pppd/pppoe.conf'
pppoe_chap_secrets = r'/run/accel-pppd/pppoe.chap-secrets'


def base_ifname(ifname):
    # Get the base interface name without VLAN
    return ifname.split('.')[0]


def convert_pado_delay(pado_delay):
    new_pado_delay = {'delays_without_sessions': [],
                      'delays_with_sessions': []}
    for delay, sessions in pado_delay.items():
        if not sessions:
            new_pado_delay['delays_without_sessions'].append(delay)
        else:
            new_pado_delay['delays_with_sessions'].append((delay, int(sessions['sessions'])))
    return new_pado_delay

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'pppoe-server']

    # retrieve common dictionary keys
    pppoe = get_accel_dict(conf, base, pppoe_chap_secrets)

    vpp_interface_base = ['vpp', 'settings', 'interface']
    if conf.exists(vpp_interface_base) and is_systemd_service_active('vpp.service'):
        vpp_ifaces = conf.get_config_dict(
            vpp_interface_base,
            key_mangling=('-', '_'),
            get_first_key=True,
            no_tag_node_value_mangle=True,
        )
        pppoe['vpp_ifaces'] = vpp_ifaces
        for interface in pppoe.get('interface', {}):
            if base_ifname(interface) in vpp_ifaces:
                pppoe['interface'][interface]['vpp_cp'] = {}

    pppoe['vpp_cp_interfaces'] = {
        'add': [
            ifname
            for ifname, iface_conf in pppoe.get('interface', {}).items()
            if 'vpp_cp' in iface_conf
        ],
        'delete': [
            iface
            for iface in node_changed(conf, base + ['interface'])
            if base_ifname(iface) in pppoe.get('vpp_ifaces', {})
        ],
    }

    if not conf.exists(base):
        pppoe['remove'] = True
        return pppoe

    if dict_search('client_ip_pool', pppoe):
        # Multiple named pools require ordered values T5099
        pppoe['ordered_named_pools'] = get_pools_in_order(dict_search('client_ip_pool', pppoe))

    if dict_search('pado_delay', pppoe):
        pado_delay = dict_search('pado_delay', pppoe)
        pppoe['pado_delay'] = convert_pado_delay(pado_delay)

    # reload-or-restart is not implemented in accel-ppp
    # use this workaround until it will be implemented
    # https://phabricator.accel-ppp.org/T3
    changed_vpp_ifaces = node_changed(
        conf, vpp_interface_base, expand_nodes=Diff.DELETE | Diff.ADD
    )
    conditions = [
        is_node_changed(conf, base + ['client-ip-pool']),
        is_node_changed(conf, base + ['client-ipv6-pool']),
        is_node_changed(conf, base + ['interface']),
        is_node_changed(conf, base + ['authentication', 'radius', 'dynamic-author']),
        is_node_changed(conf, base + ['authentication', 'mode']),
        any(
            base_ifname(iface) in changed_vpp_ifaces
            for iface in pppoe.get('interface', {})
        ),
    ]
    if any(conditions):
        pppoe.update({'restart_required': {}})
    pppoe['server_type'] = 'pppoe'
    return pppoe

def verify_pado_delay(pppoe):
    if 'pado_delay' in pppoe:
        pado_delay = pppoe['pado_delay']

        delays_without_sessions = pado_delay['delays_without_sessions']
        if 'disable' in delays_without_sessions:
            raise ConfigError(
                'Number of sessions must be specified for "pado-delay disable"'
            )

        if len(delays_without_sessions) > 1:
            raise ConfigError(
                f'Cannot add more then ONE pado-delay without sessions, '
                f'but {len(delays_without_sessions)} were set'
            )

        if 'disable' in [delay[0] for delay in pado_delay['delays_with_sessions']]:
            # need to sort delays by sessions to verify if there is no delay
            # for sessions after disabling
            sorted_pado_delay = sorted(pado_delay['delays_with_sessions'], key=lambda k_v: k_v[1])
            last_delay = sorted_pado_delay[-1]

            if last_delay[0] != 'disable':
                raise ConfigError(
                    f'Cannot add pado-delay after disabled sessions, but '
                    f'"pado-delay {last_delay[0]} sessions {last_delay[1]}" was set'
                )

def verify(pppoe):
    if 'remove' in pppoe:
        return None

    verify_accel_ppp_authentication(pppoe)
    verify_accel_ppp_ip_pool(pppoe)
    verify_accel_ppp_name_servers(pppoe)
    verify_accel_ppp_wins_servers(pppoe)
    verify_pado_delay(pppoe)

    if 'interface' not in pppoe:
        raise ConfigError('At least one listen interface must be defined!')

    # Check is interface exists in the system
    for interface, interface_config in pppoe['interface'].items():
        # Interfaces integrated with the control-plane in VPP must exist in the system
        warning_only = 'vpp_cp' not in interface_config
        verify_interface_exists(pppoe, interface, warning_only=warning_only)

        if 'vlan_mon' in interface_config and base_ifname(interface) in pppoe.get(
            'vpp_ifaces', {}
        ):
            raise ConfigError(
                f'Cannot set option "vlan-mon": interface {interface} is integrated with control-plane!'
            )

        if 'vlan_mon' in interface_config and not 'vlan' in interface_config:
            raise ConfigError('Option "vlan-mon" requires "vlan" to be set!')

    return None


def generate(pppoe):
    if 'remove' in pppoe:
        return None

    render(pppoe_conf, 'accel-ppp/pppoe.config.j2', pppoe)

    if dict_search('authentication.mode', pppoe) == 'local':
        render(pppoe_chap_secrets, 'accel-ppp/chap-secrets.config_dict.j2',
               pppoe, permission=0o640)
    return None


def apply(pppoe):
    systemd_service = 'accel-ppp@pppoe.service'

    # delete pppoe mapping in vpp
    vpp_cp_ifaces_delete = pppoe.get('vpp_cp_interfaces', {}).get('delete', [])
    if 'vpp_ifaces' in pppoe and vpp_cp_ifaces_delete:
        vpp = VPPControl()
        for iface in vpp_cp_ifaces_delete:
            vpp.map_pppoe_interface(iface, is_add=False)

    if 'remove' in pppoe:
        call(f'systemctl stop {systemd_service}')
        for file in [pppoe_conf, pppoe_chap_secrets]:
            if os.path.exists(file):
                os.unlink(file)
        return None

    if 'restart_required' in pppoe:
        call(f'systemctl restart {systemd_service}')
    else:
        call(f'systemctl reload-or-restart {systemd_service}')

    # add pppoe mapping in vpp
    vpp_cp_ifaces_add = pppoe.get('vpp_cp_interfaces', {}).get('add', [])
    if vpp_cp_ifaces_add:
        vpp = VPPControl()
        for iface in vpp_cp_ifaces_add:
            vpp.map_pppoe_interface(iface, is_add=True)


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
