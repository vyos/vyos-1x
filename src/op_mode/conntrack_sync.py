#!/usr/bin/env python3
#
# Copyright (C) 2022-2024 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import syslog
import xmltodict

import vyos.opmode

from vyos.configquery import CliShellApiConfigQuery
from vyos.configquery import ConfigTreeQuery
from vyos.utils.commit import commit_in_progress
from vyos.utils.process import call
from vyos.utils.process import cmd
from vyos.utils.process import run
from vyos.template import render_to_string

conntrackd_bin = '/usr/sbin/conntrackd'
conntrackd_config = '/run/conntrackd/conntrackd.conf'
failover_state_file = '/var/run/vyatta-conntrackd-failover-state'

def is_configured():
    """ Check if conntrack-sync service is configured """
    config = CliShellApiConfigQuery()
    if not config.exists(['service', 'conntrack-sync']):
        raise vyos.opmode.UnconfiguredSubsystem("conntrack-sync is not configured!")

def send_bulk_update():
    """ send bulk update of internal-cache to other systems """
    tmp = run(f'{conntrackd_bin} -C {conntrackd_config} -B')
    if tmp > 0:
        raise vyos.opmode.Error('Failed to send bulk update to other conntrack-sync systems')

def request_sync():
    """ request resynchronization with other systems """
    tmp = run(f'{conntrackd_bin} -C {conntrackd_config} -n')
    if tmp > 0:
        raise vyos.opmode.Error('Failed to request resynchronization of external cache')

def flush_cache(direction):
    """ flush conntrackd cache (internal or external) """
    if direction not in ['internal', 'external']:
        raise ValueError()
    tmp = run(f'{conntrackd_bin} -C {conntrackd_config} -f {direction}')
    if tmp > 0:
        raise vyos.opmode.Error('Failed to clear {direction} cache')

def from_xml(raw, xml):
    out = []
    for line in xml.splitlines():
        if line == '\n':
            continue
        parsed = xmltodict.parse(line)
        out.append(parsed)

    if raw:
        return out
    else:
        return render_to_string('conntrackd/conntrackd.op-mode.j2', {'data' : out})

def restart():
    is_configured()
    if commit_in_progress():
        raise vyos.opmode.CommitInProgress('Cannot restart conntrackd while a commit is in progress')

    syslog.syslog('Restarting conntrack sync service...')
    cmd('systemctl restart conntrackd.service')
    # request resynchronization with other systems
    request_sync()
    # send bulk update of internal-cache to other systems
    send_bulk_update()

def reset_external_cache():
    is_configured()
    syslog.syslog('Resetting external cache of conntrack sync service...')

    # flush the external cache
    flush_cache('external')
    # request resynchronization with other systems
    request_sync()

def reset_internal_cache():
    is_configured()
    syslog.syslog('Resetting internal cache of conntrack sync service...')
    # flush the internal cache
    flush_cache('internal')

    # request resynchronization of internal cache with kernel conntrack table
    tmp = run(f'{conntrackd_bin} -C {conntrackd_config} -R')
    if tmp > 0:
        print('ERROR: failed to resynchronize internal cache with kernel conntrack table')

    # send bulk update of internal-cache to other systems
    send_bulk_update()

def _show_cache(raw, opts):
    is_configured()
    out = cmd(f'{conntrackd_bin} -C {conntrackd_config} {opts} -x')
    return from_xml(raw, out)

def show_external_cache(raw: bool):
    opts = '-e ct'
    return _show_cache(raw, opts)

def show_external_expect(raw: bool):
    opts = '-e expect'
    return _show_cache(raw, opts)

def show_internal_cache(raw: bool):
    opts = '-i ct'
    return _show_cache(raw, opts)

def show_internal_expect(raw: bool):
    opts = '-i expect'
    return _show_cache(raw, opts)

def show_statistics(raw: bool):
    if raw:
        raise vyos.opmode.UnsupportedOperation("Machine-readable conntrack-sync statistics are not available yet")
    else:
        is_configured()
        config = ConfigTreeQuery()
        print('\nMain Table Statistics:\n')
        call(f'{conntrackd_bin} -C {conntrackd_config} -s')
        print()
        if config.exists(['service', 'conntrack-sync', 'expect-sync']):
            print('\nExpect Table Statistics:\n')
            call(f'{conntrackd_bin} -C {conntrackd_config} -s exp')
            print()

def show_status(raw: bool):
    is_configured()
    config = ConfigTreeQuery()
    ct_sync_intf = config.list_nodes(['service', 'conntrack-sync', 'interface'])
    ct_sync_intf = ', '.join(ct_sync_intf)
    failover_state = "no transition yet!"
    expect_sync_protocols = []

    if config.exists(['service', 'conntrack-sync', 'failover-mechanism', 'vrrp']):
        failover_mechanism = "vrrp"
        vrrp_sync_grp = config.value(['service', 'conntrack-sync', 'failover-mechanism', 'vrrp', 'sync-group'])

    if os.path.isfile(failover_state_file):
        with open(failover_state_file, "r") as f:
            failover_state = f.readline()

    if config.exists(['service', 'conntrack-sync', 'expect-sync']):
        expect_sync_protocols = config.values(['service', 'conntrack-sync', 'expect-sync'])
        if 'all' in expect_sync_protocols:
            expect_sync_protocols = ["ftp", "sip", "h323", "nfs", "sqlnet"]

    if raw:
        status_data = {
            "sync_interface": ct_sync_intf,
            "failover_mechanism": failover_mechanism,
            "sync_group": vrrp_sync_grp,
            "last_transition": failover_state,
            "sync_protocols": expect_sync_protocols
        }

        return status_data
    else:
        if expect_sync_protocols:
            expect_sync_protocols = ', '.join(expect_sync_protocols)
        else:
            expect_sync_protocols = "disabled"
        show_status = (f'\nsync-interface        : {ct_sync_intf}\n'
                       f'failover-mechanism    : {failover_mechanism} [sync-group {vrrp_sync_grp}]\n'
                       f'last state transition : {failover_state}\n'
                       f'ExpectationSync       : {expect_sync_protocols}')

        return show_status

if __name__ == '__main__':
    syslog.openlog(ident='conntrack-tools', logoption=syslog.LOG_PID, facility=syslog.LOG_INFO)

    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
