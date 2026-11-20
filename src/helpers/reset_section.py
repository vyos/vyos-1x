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
#
#


import argparse
import sys
import os
import grp
from pathlib import Path

from vyos.configsession import ConfigSession
from vyos.config import Config
from vyos.configdiff import get_config_diff
from vyos.xml_ref import is_leaf
from vyos.utils.commit import wait_for_commit_lock
from vyos.defaults import vpp_failure_handler_marker


CFG_GROUP = 'vyattacfg'
DEBUG = False


def type_str_to_list(value):
    if isinstance(value, str):
        res = value.split()
        if res:
            return res
    raise argparse.ArgumentTypeError(
        'path must be a non-empty whitespace separated string'
    )


parser = argparse.ArgumentParser()
parser.add_argument('path', type=type_str_to_list, help='section to reload/rollback')
parser.add_argument('--pid', help='pid of config session')

group = parser.add_mutually_exclusive_group()
group.add_argument('--reload', action='store_true', help='retry proposed commit')
group.add_argument(
    '--rollback', action='store_true', default=True, help='rollback to stable commit'
)

args = parser.parse_args()

path = args.path
reload = args.reload
rollback = args.rollback
pid = args.pid

try:
    if is_leaf(path):
        sys.exit('path is leaf node: neither allowed nor useful')
except ValueError:
    if DEBUG:
        sys.exit('nonexistent path: neither allowed nor useful')
    else:
        sys.exit()

test = Config()
in_session = test.in_session()

if in_session:
    if reload:
        sys.exit('reset_section reload not available inside of a config session')

    diff = get_config_diff(test)
    if not diff.is_node_changed(path):
        # No discrepancies at path after commit, hence no error to revert.
        sys.exit()

    del diff
else:
    if not reload:
        sys.exit('reset_section rollback not available outside of a config session')

del test


session_id = int(pid) if pid else os.getpid()

if in_session:
    # check hint left by vyshim when ConfigError is from apply stage
    hint_name = f'/tmp/apply_{session_id}'
    if not os.path.exists(hint_name):
        # no apply error; exit
        sys.exit()
    else:
        # cleanup hint and continue with reset
        os.unlink(hint_name)

cfg_group = grp.getgrnam(CFG_GROUP)
os.setgid(cfg_group.gr_gid)
os.umask(0o002)

wait_for_commit_lock()

shared = not bool(reload)

session = ConfigSession(session_id, shared=shared)

session_env = session.get_session_env()
config = Config(session_env)

d = config.get_config_dict(path, effective=True, get_first_key=True)

if in_session:
    session.discard()

if path[0] == 'vpp':
    Path(vpp_failure_handler_marker).touch()

try:
    session.delete(path)
    session.commit()
finally:
    if path[0] == 'vpp':
        Path(vpp_failure_handler_marker).unlink(missing_ok=True)

if not d:
    # nothing more to do in either case of reload/rollback
    sys.exit()

session.set_section(path, d)
out = session.commit()
print(out)
