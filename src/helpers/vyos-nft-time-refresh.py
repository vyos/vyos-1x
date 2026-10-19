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

# nft converts "meta hour" to UTC when a ruleset is loaded, using the UTC
# offset of that moment. After a daylight saving change every hour window is
# off by the difference until the rules are loaded again. This helper loads
# only the affected rules again, in place, so sets and counters are kept, and
# arms itself for the next change of the UTC offset.

import argparse
import json
import re
import sys

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from zoneinfo import ZoneInfo

from vyos.defaults import nft_time_refresh
from vyos.utils.commit import acquire_commit_lock_file
from vyos.utils.commit import release_commit_lock_file
from vyos.utils.process import cmdl
from vyos.utils.process import rc_cmd

# rendered by conf_mode/firewall.py and conf_mode/policy_route.py
rule_files = ['/run/nftables.conf', '/run/nftables_policy.conf']
unit_prefix = 'vyos-nft-time-refresh'

table_re = re.compile(r'^\s*table\s+(\S+)\s+(\S+)\s*\{')
chain_re = re.compile(r'^\s*chain\s+(\S+)\s*\{')
comment_re = re.compile(r'comment "([^"]+)"')

def hour_rules(path: str) -> dict:
    """Return {(family, table, chain, comment): rule} for rules with an hour match"""
    rules = {}
    family = table = chain = None
    try:
        with open(path) as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return rules

    for line in lines:
        if match := table_re.match(line):
            family, table = match.groups()
            chain = None
        elif match := chain_re.match(line):
            chain = match.group(1)
        elif chain and 'hour "' in line and (match := comment_re.search(line)):
            rules[(family, table, chain, match.group(1))] = line.strip()
    return rules

def all_hour_rules() -> dict:
    rules = {}
    for path in rule_files:
        rules.update(hour_rules(path))
    return rules

def rule_handles(family: str, table: str) -> dict:
    """Return {(family, table, chain, comment): handle} of a loaded table"""
    handles = {}
    rc, out = rc_cmd(f'nft -j -a list table {family} {table}')
    if rc != 0:
        return handles
    for item in json.loads(out)['nftables']:
        rule = item.get('rule')
        if rule and 'comment' in rule:
            key = (rule['family'], rule['table'], rule['chain'], rule['comment'])
            handles[key] = rule['handle']
    return handles

def replace_batch(rules: dict) -> list:
    """nft commands replacing every rendered hour rule found in the ruleset"""
    batch = []
    handles = {}
    for family, table in {(k[0], k[1]) for k in rules}:
        handles.update(rule_handles(family, table))
    for key, rule in sorted(rules.items()):
        if key in handles:
            family, table, chain, _ = key
            batch.append(f'replace rule {family} {table} {chain} handle {handles[key]} {rule}')
    return batch

def next_offset_change(now: datetime, tz: ZoneInfo, horizon_days=400):
    """First moment after now with a different UTC offset, or None"""
    offset = now.astimezone(tz).utcoffset()
    lo = now
    for _ in range(horizon_days):
        hi = lo + timedelta(days=1)
        if hi.astimezone(tz).utcoffset() != offset:
            # narrow down to the second
            while hi - lo > timedelta(seconds=1):
                mid = lo + (hi - lo) / 2
                if mid.astimezone(tz).utcoffset() == offset:
                    lo = mid
                else:
                    hi = mid
            return hi.replace(microsecond=0)
        lo = hi
    return None

def arm():
    """Schedule a refresh at the next UTC offset change if any rule needs it"""
    # stopping only the timers keeps a refresh which is running right now
    rc_cmd(f"systemctl stop '{unit_prefix}-*.timer'")
    if not all_hour_rules():
        return

    with open('/etc/localtime', 'rb') as f:
        tz = ZoneInfo.from_file(f)
    change = next_offset_change(datetime.now(timezone.utc), tz)
    if not change:
        return

    when = change + timedelta(seconds=5)
    # unique unit name - the unit of a running refresh still exists while it
    # arms the next one
    unit = f'{unit_prefix}-{int(when.timestamp())}'
    # timers default to AccuracySec=1min, which leaves a window up to a minute long
    cmdl(['systemd-run', f'--unit={unit}', '--timer-property=RemainAfterElapse=no',
          '--timer-property=AccuracySec=1s',
          f'--on-calendar={when:%Y-%m-%d %H:%M:%S} UTC', nft_time_refresh, '--refresh'])

def refresh():
    batch = replace_batch(all_hour_rules())
    if not batch:
        return
    rc, out = rc_cmd('nft -f -', input='\n'.join(batch) + '\n')
    if rc != 0:
        print(f'Failed to refresh time based rules: {out}', file=sys.stderr)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--arm', action='store_true', help='Schedule a refresh for the next UTC offset change')
    group.add_argument('--refresh', action='store_true', help='Load rules with an hour match again')
    args = parser.parse_args()

    if args.arm:
        arm()
        sys.exit(0)

    # a commit loads the rules itself and arms the next refresh
    lock, _ = acquire_commit_lock_file()
    if lock is None:
        sys.exit(0)
    try:
        refresh()
        arm()
    finally:
        release_commit_lock_file(lock)
