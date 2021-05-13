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

from argparse import ArgumentParser
from vyos.configquery import CliShellApiConfigQuery
from vyos.util import call
from vyos.util import run

conntrackd_bin = '/usr/sbin/conntrackd'
conntrackd_config = '/run/conntrackd/conntrackd.conf'

parser = ArgumentParser(description='Conntrack Sync')
parser.add_argument('--restart', help='Restart connection tracking synchronization service', action='store_true')
parser.add_argument('--reset-cache-internal', help='Reset internal cache', action='store_true')
parser.add_argument('--reset-cache-external', help='Reset external cache', action='store_true')

def is_configured():
    """ Check if conntrack-sync service is configured """
    config = CliShellApiConfigQuery()
    if not config.exists(['service', 'conntrack-sync']):
        print('Service conntrackd-sync not configured!')
        exit(1)

def send_bulk_update():
    """ send bulk update of internal-cache to other systems """
    tmp = run(f'{conntrackd_bin} -c {conntrackd_config} -B')
    if tmp > 0:
        print('ERROR: failed to send bulk update to other conntrack-sync systems')

def request_sync():
    """ request resynchronization with other systems """
    tmp = run(f'{conntrackd_bin} -c {conntrackd_config} -n')
    if tmp > 0:
        print('ERROR: failed to request resynchronization of external cache')

def flush_cache(direction):
    """ flush conntrackd cache (internal or external) """
    if direction not in ['internal', 'external']:
        raise ValueError()
    tmp = run(f'{conntrackd_bin} -c {conntrackd_config} -f {direction}')
    if tmp > 0:
        print('ERROR: failed to clear {direction} cache')

if __name__ == '__main__':
    args = parser.parse_args()
    syslog.openlog(ident='conntrack-tools', logoption=syslog.LOG_PID,
                   facility=syslog.LOG_INFO)

    if args.restart:
        is_configured()

        syslog.syslog('Restarting conntrack sync service...')
        call('systemctl restart conntrackd.service')
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
        tmp = run(f'{conntrackd_bin} -c {conntrackd_config} -R')
        if tmp > 0:
            print('ERROR: failed to resynchronize internal cache with kernel conntrack table')

        # send bulk update of internal-cache to other systems
        send_bulk_update()

    else:
        parser.print_help()
        exit(1)
