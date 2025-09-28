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
import time

from vyos.ifconfig.interface import Interface
from vyos.utils.network import get_bridge_master
from vyos.utils.network import is_mpls_enabled
from vyos.utils.process import cmd
from vyos.utils.process import rc_cmd
from vyos.utils.system import sysctl_write
from vyos.utils.dict import dict_search

def build_sub_int_list(interface: str, networks: list[str]):
    sub_int_list = {}
    for network in networks:
        sub_int = f'{interface}.{network[:5]}'
        sub_int_list[sub_int] = {}
        sub_int_list[sub_int]['bridges'] = get_bridge_master(sub_int)
        sub_int_list[sub_int]['mpls'] = is_mpls_enabled(sub_int)
    return sub_int_list

def wait_for_interface(sub_int_list: dict):
    # Give the interfaces time to start
    timeout = 10
    interval = 1
    for restart_int, restart_config in sub_int_list.items():
        is_member = dict_search('bridges', restart_config)
        is_mpls = dict_search('mpls', restart_config)

        end = time.monotonic() + timeout
        while time.monotonic() < end:
            rc, output = rc_cmd(f'ip link show dev {restart_int}')
            if rc != 0:
                time.sleep(interval)
                continue
            break

        # After a restart, the interface would be removed as a bridge member.
        # Re-add the interface as a bridge member
        if is_member:
            cmd(f'ip link set {restart_int} master {is_member}')

        # After a restart, the interface would be removed as a MPLS interface.
        # Re-add the interface as a MPLS interface
        if is_mpls:
            sys_interface = restart_int.replace(".", "/")
            sysctl_write(f'net.mpls.conf.{sys_interface}.input', 1)

@Interface.register
class ZeroTierIf(Interface):
    iftype = 'zerotier'
    definition = {
        **Interface.definition,
        **{
            'section': 'zerotier',
            'prefixes': ['zt', ],
        },
    }
