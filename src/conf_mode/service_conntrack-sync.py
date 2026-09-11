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
from vyos.configverify import verify_interface_exists
from vyos.utils.dict import dict_search
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file
from vyos.utils.process import call
from vyos.utils.process import run
from vyos.template import render
from vyos.template import get_ipv4
from vyos.template import get_ipv6
from vyos.template import is_ipv4
from vyos.utils.network import is_addr_assigned
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = '/run/conntrackd/conntrackd.conf'

def resync_vrrp():
    tmp = run('/usr/libexec/vyos/conf_mode/high-availability.py')
    if tmp > 0:
        print('ERROR: error restarting VRRP daemon!')

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'conntrack-sync']
    if not conf.exists(base):
        return None

    conntrack = conf.get_config_dict(base, key_mangling=('-', '_'),
                                     get_first_key=True, with_defaults=True)

    conntrack['hash_size'] = read_file('/sys/module/nf_conntrack/parameters/hashsize')
    conntrack['table_size'] = read_file('/proc/sys/net/netfilter/nf_conntrack_max')

    conntrack['vrrp'] = conf.get_config_dict(['high-availability', 'vrrp', 'sync-group'],
                                     get_first_key=True)

    return conntrack

def verify(conntrack):
    if not conntrack:
        return None

    if 'interface' not in conntrack:
        raise ConfigError('Interface not defined!')

    has_peer = False
    for interface, interface_config in conntrack['interface'].items():
        verify_interface_exists(conntrack, interface)
        if 'peer' in interface_config:
            has_peer = True

    # If one interface runs in unicast mode instead of multicast, so must all the
    # others, else conntrackd will error out with: "cannot use UDP with other
    # dedicated link protocols"
    if has_peer:
        for interface, interface_config in conntrack['interface'].items():
            if 'peer' not in interface_config:
                raise ConfigError('Cannot mix unicast and multicast mode!')

    # The synchronization interface must have an address matching the address
    # family selected by its peer or multicast group.
    for interface, interface_config in conntrack['interface'].items():
        sync_address = (
            interface_config['peer'] if has_peer else conntrack['mcast_group']
        )
        address_family = 'IPv4' if is_ipv4(sync_address) else 'IPv6'
        interface_addresses = (
            get_ipv4(interface) if is_ipv4(sync_address) else get_ipv6(interface)
        )
        if not interface_addresses:
            raise ConfigError(
                f'Interface {interface} requires an {address_family} address!'
            )

    if 'expect_sync' in conntrack:
        if len(conntrack['expect_sync']) > 1 and 'all' in conntrack['expect_sync']:
            raise ConfigError('Cannot configure expect-sync "all" with other protocols!')

    if 'listen_address' in conntrack:
        for address in conntrack['listen_address']:
            if not is_addr_assigned(address):
                raise ConfigError(f'Specified listen-address {address} not assigned to any interface!')
            if has_peer:
                for interface_config in conntrack['interface'].values():
                    peer = interface_config['peer']
                    if is_ipv4(address) != is_ipv4(peer):
                        raise ConfigError(
                            f'Listen-address {address} does not match '
                            f'address-family of peer {peer}!'
                        )

    vrrp_group = dict_search('failover_mechanism.vrrp.sync_group', conntrack)
    if vrrp_group == None:
        raise ConfigError(f'No VRRP sync-group defined!')
    if vrrp_group not in conntrack['vrrp']:
        raise ConfigError(f'VRRP sync-group {vrrp_group} not configured!')

    return None

def generate(conntrack):
    if not conntrack:
        if os.path.isfile(config_file):
            os.unlink(config_file)
        return None

    render(config_file, 'conntrackd/conntrackd.conf.j2', conntrack)

    return None

def apply(conntrack):
    systemd_service = 'conntrackd.service'
    if not conntrack:
        # Failover mechanism daemon should be indicated that it no longer needs
        # to execute conntrackd actions on transition. This is only required
        # once when conntrackd is stopped and taken out of service!
        if process_named_running('conntrackd'):
            resync_vrrp()

        call(f'systemctl stop {systemd_service}')
        return None

    # Failover mechanism daemon should be indicated that it needs to execute
    # conntrackd actions on transition. This is only required once when conntrackd
    # is started the first time!
    if not process_named_running('conntrackd'):
        resync_vrrp()

    call(f'systemctl reload-or-restart {systemd_service}')
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
