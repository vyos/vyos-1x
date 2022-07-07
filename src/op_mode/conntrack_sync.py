#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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
import syslog
import xmltodict

from argparse import ArgumentParser
from vyos.configquery import CliShellApiConfigQuery
from vyos.configquery import ConfigTreeQuery
from vyos.util import call
from vyos.util import commit_in_progress
from vyos.util import cmd
from vyos.util import run
from vyos.template import render_to_string

conntrackd_bin = '/usr/sbin/conntrackd'
conntrackd_config = '/run/conntrackd/conntrackd.conf'
failover_state_file = '/var/run/vyatta-conntrackd-failover-state'

parser = ArgumentParser(description='Conntrack Sync')
group = parser.add_mutually_exclusive_group()
group.add_argument('--restart', help='Restart connection tracking synchronization service', action='store_true')
group.add_argument('--reset-cache-internal', help='Reset internal cache', action='store_true')
group.add_argument('--reset-cache-external', help='Reset external cache', action='store_true')
group.add_argument('--show-internal', help='Show internal (main) tracking cache', action='store_true')
group.add_argument('--show-external', help='Show external (main) tracking cache', action='store_true')
group.add_argument('--show-internal-expect', help='Show internal (expect) tracking cache', action='store_true')
group.add_argument('--show-external-expect', help='Show external (expect) tracking cache', action='store_true')
group.add_argument('--show-statistics', help='Show connection syncing statistics', action='store_true')
group.add_argument('--show-status', help='Show conntrack-sync status', action='store_true')

def is_configured():
    """ Check if conntrack-sync service is configured """
    config = CliShellApiConfigQuery()
    if not config.exists(['service', 'conntrack-sync']):
        print('Service conntrackd-sync not configured!')
        exit(1)

def send_bulk_update():
    """ send bulk update of internal-cache to other systems """
    tmp = run(f'{conntrackd_bin} -C {conntrackd_config} -B')
    if tmp > 0:
        print('ERROR: failed to send bulk update to other conntrack-sync systems')

def request_sync():
    """ request resynchronization with other systems """
    tmp = run(f'{conntrackd_bin} -C {conntrackd_config} -n')
    if tmp > 0:
        print('ERROR: failed to request resynchronization of external cache')

def flush_cache(direction):
    """ flush conntrackd cache (internal or external) """
    if direction not in ['internal', 'external']:
        raise ValueError()
    tmp = run(f'{conntrackd_bin} -C {conntrackd_config} -f {direction}')
    if tmp > 0:
        print('ERROR: failed to clear {direction} cache')

def xml_to_stdout(xml):
    out = []
    for line in xml.splitlines():
        if line == '\n':
            continue
        parsed = xmltodict.parse(line)
        out.append(parsed)

    print(render_to_string('conntrackd/conntrackd.op-mode.j2', {'data' : out}))

if __name__ == '__main__':
    args = parser.parse_args()
    syslog.openlog(ident='conntrack-tools', logoption=syslog.LOG_PID,
                   facility=syslog.LOG_INFO)

    if args.restart:
        is_configured()
        if commit_in_progress():
            print('Cannot restart conntrackd while a commit is in progress')
            exit(1)

        syslog.syslog('Restarting conntrack sync service...')
        cmd('systemctl restart conntrackd.service')
        # request resynchronization with other systems
        request_sync()
        # send bulk update of internal-cache to other systems
        send_bulk_update()

    elif args.reset_cache_external:
        is_configured()
        syslog.syslog('Resetting external cache of conntrack sync service...')

        # flush the external cache
        flush_cache('external')
        # request resynchronization with other systems
        request_sync()

    elif args.reset_cache_internal:
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

    elif args.show_external or args.show_internal or args.show_external_expect or args.show_internal_expect:
        is_configured()
        opt = ''
        if args.show_external:
            opt = '-e ct'
        elif args.show_external_expect:
            opt = '-e expect'
        elif args.show_internal:
            opt = '-i ct'
        elif args.show_internal_expect:
            opt = '-i expect'

        if args.show_external or args.show_internal:
            print('Main Table Entries:')
        else:
            print('Expect Table Entries:')
        out = cmd(f'sudo {conntrackd_bin} -C {conntrackd_config} {opt} -x')
        xml_to_stdout(out)

    elif args.show_statistics:
        is_configured()
        config = ConfigTreeQuery()
        print('\nMain Table Statistics:\n')
        call(f'sudo {conntrackd_bin} -C {conntrackd_config} -s')
        print()
        if config.exists(['service', 'conntrack-sync', 'expect-sync']):
            print('\nExpect Table Statistics:\n')
            call(f'sudo {conntrackd_bin} -C {conntrackd_config} -s exp')
            print()

    elif args.show_status:
        is_configured()
        config = ConfigTreeQuery()
        ct_sync_intf = config.list_nodes(['service', 'conntrack-sync', 'interface'])
        ct_sync_intf = ', '.join(ct_sync_intf)
        failover_state = "no transition yet!"
        expect_sync_protocols = "disabled"

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
            expect_sync_protocols = ', '.join(expect_sync_protocols)

        show_status = (f'\nsync-interface        : {ct_sync_intf}\n'
                       f'failover-mechanism    : {failover_mechanism} [sync-group {vrrp_sync_grp}]\n'
                       f'last state transition : {failover_state}'
                       f'ExpectationSync       : {expect_sync_protocols}')

        print(show_status)

    else:
        parser.print_help()
        exit(1)
