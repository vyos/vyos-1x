# Copyright 2023-2024 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

import os
import re
import sys
import gzip
import logging

from typing import Optional
from typing import Tuple
from filecmp import cmp
from datetime import datetime
from textwrap import dedent
from pathlib import Path
from tabulate import tabulate
from shutil import copy, chown
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

from vyos.config import Config
from vyos.configtree import ConfigTree
from vyos.configtree import ConfigTreeError
from vyos.configtree import show_diff
from vyos.load_config import load
from vyos.load_config import LoadConfigError
from vyos.defaults import directories
from vyos.version import get_full_version_data
from vyos.utils.io import ask_yes_no
from vyos.utils.boot import boot_configuration_complete
from vyos.utils.process import is_systemd_service_active
from vyos.utils.process import rc_cmd

SAVE_CONFIG = '/usr/libexec/vyos/vyos-save-config.py'
config_json = '/run/vyatta/config/config.json'

# created by vyatta-cfg-postinst
commit_post_hook_dir = '/etc/commit/post-hooks.d'

commit_hooks = {'commit_revision': '01vyos-commit-revision',
                'commit_archive': '02vyos-commit-archive'}

DEFAULT_TIME_MINUTES = 10
timer_name = 'commit-confirm'

config_file = os.path.join(directories['config'], 'config.boot')
archive_dir = os.path.join(directories['config'], 'archive')
archive_config_file = os.path.join(archive_dir, 'config.boot')
commit_log_file = os.path.join(archive_dir, 'commits')
logrotate_conf = os.path.join(archive_dir, 'lr.conf')
logrotate_state = os.path.join(archive_dir, 'lr.state')
rollback_config = os.path.join(archive_dir, 'config.boot-rollback')
prerollback_config = os.path.join(archive_dir, 'config.boot-prerollback')
tmp_log_entry = '/tmp/commit-rev-entry'

logger = logging.getLogger('config_mgmt')
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(funcName)s: %(levelname)s:%(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

def save_config(target, json_out=None):
    if json_out is None:
        cmd = f'{SAVE_CONFIG} {target}'
    else:
        cmd = f'{SAVE_CONFIG} {target} --write-json-file {json_out}'
    rc, out = rc_cmd(cmd)
    if rc != 0:
        logger.critical(f'save config failed: {out}')

def unsaved_commits() -> bool:
    if get_full_version_data()['boot_via'] == 'livecd':
        return False
    tmp_save = '/tmp/config.running'
    save_config(tmp_save)
    ret = not cmp(tmp_save, config_file, shallow=False)
    os.unlink(tmp_save)
    return ret

def get_file_revision(rev: int):
    revision = os.path.join(archive_dir, f'config.boot.{rev}.gz')
    try:
        with gzip.open(revision) as f:
            r = f.read().decode()
    except FileNotFoundError:
        logger.warning(f'commit revision {rev} not available')
        return ''
    return r

def get_config_tree_revision(rev: int):
    c = get_file_revision(rev)
    return ConfigTree(c)

def is_node_revised(path: list = [], rev1: int = 1, rev2: int = 0) -> bool:
    from vyos.configtree import DiffTree
    left = get_config_tree_revision(rev1)
    right = get_config_tree_revision(rev2)
    diff_tree = DiffTree(left, right)
    if diff_tree.add.exists(path) or diff_tree.sub.exists(path):
        return True
    return False

class ConfigMgmtError(Exception):
    pass

class ConfigMgmt:
    def __init__(self, session_env=None, config=None):
        if session_env:
            self._session_env = session_env
        else:
            self._session_env = None

        if config is None:
            config = Config()

        d = config.get_config_dict(['system', 'config-management'],
                                   key_mangling=('-', '_'),
                                   get_first_key=True)

        self.max_revisions = int(d.get('commit_revisions', 0))
        self.num_revisions = 0
        self.locations = d.get('commit_archive', {}).get('location', [])
        self.source_address = d.get('commit_archive',
                                    {}).get('source_address', '')
        if config.exists(['system', 'host-name']):
            self.hostname = config.return_value(['system', 'host-name'])
            if config.exists(['system', 'domain-name']):
                tmp = config.return_value(['system', 'domain-name'])
                self.hostname += f'.{tmp}'
        else:
            self.hostname = 'vyos'

        # upload only on existence of effective values, notably, on boot.
        # one still needs session self.locations (above) for setting
        # post-commit hook in conf_mode script
        path = ['system', 'config-management', 'commit-archive', 'location']
        if config.exists_effective(path):
            self.effective_locations = config.return_effective_values(path)
        else:
            self.effective_locations = []

        # a call to compare without args is edit_level aware
        edit_level = os.getenv('VYATTA_EDIT_LEVEL', '')
        self.edit_path = [l for l in edit_level.split('/') if l]

        self.active_config = config._running_config
        self.working_config = config._session_config

    # Console script functions
    #
    def commit_confirm(self, minutes: int=DEFAULT_TIME_MINUTES,
                       no_prompt: bool=False) -> Tuple[str,int]:
        """Commit with reboot to saved config in 'minutes' minutes if
        'confirm' call is not issued.
        """
        if is_systemd_service_active(f'{timer_name}.timer'):
            msg = 'Another confirm is pending'
            return msg, 1

        if unsaved_commits():
            W = '\nYou should save previous commits before commit-confirm !\n'
        else:
            W = ''

        prompt_str = f'''
commit-confirm will automatically reboot in {minutes} minutes unless changes
are confirmed.\n
Proceed ?'''
        prompt_str = W + prompt_str
        if not no_prompt and not ask_yes_no(prompt_str, default=True):
            msg = 'commit-confirm canceled'
            return msg, 1

        action = 'sg vyattacfg "/usr/bin/config-mgmt revert"'
        cmd = f'sudo systemd-run --quiet --on-active={minutes}m --unit={timer_name} {action}'
        rc, out = rc_cmd(cmd)
        if rc != 0:
            raise ConfigMgmtError(out)

        # start notify
        cmd = f'sudo -b /usr/libexec/vyos/commit-confirm-notify.py {minutes}'
        os.system(cmd)

        msg = f'Initialized commit-confirm; {minutes} minutes to confirm before reboot'
        return msg, 0

    def confirm(self) -> Tuple[str,int]:
        """Do not reboot to saved config following 'commit-confirm'.
        Update commit log and archive.
        """
        if not is_systemd_service_active(f'{timer_name}.timer'):
            msg = 'No confirm pending'
            return msg, 0

        cmd = f'sudo systemctl stop --quiet {timer_name}.timer'
        rc, out = rc_cmd(cmd)
        if rc != 0:
            raise ConfigMgmtError(out)

        # kill notify
        cmd = 'sudo pkill -f commit-confirm-notify.py'
        rc, out = rc_cmd(cmd)
        if rc != 0:
            raise ConfigMgmtError(out)

        entry = self._read_tmp_log_entry()

        if self._archive_active_config():
            self._add_log_entry(**entry)
            self._update_archive()

        msg = 'Reboot timer stopped'
        return msg, 0

    def revert(self) -> Tuple[str,int]:
        """Reboot to saved config, dropping commits from 'commit-confirm'.
        """
        _ = self._read_tmp_log_entry()

        # archived config will be reverted on boot
        rc, out = rc_cmd('sudo systemctl reboot')
        if rc != 0:
            raise ConfigMgmtError(out)

        return '', 0

    def rollback(self, rev: int, no_prompt: bool=False) -> Tuple[str,int]:
        """Reboot to config revision 'rev'.
        """
        msg = ''

        if not self._check_revision_number(rev):
            msg = f'Invalid revision number {rev}: must be 0 < rev < {self.num_revisions}'
            return msg, 1

        prompt_str = 'Proceed with reboot ?'
        if not no_prompt and not ask_yes_no(prompt_str, default=True):
            msg = 'Canceling rollback'
            return msg, 0

        rc, out = rc_cmd(f'sudo cp {archive_config_file} {prerollback_config}')
        if rc != 0:
            raise ConfigMgmtError(out)

        path = os.path.join(archive_dir, f'config.boot.{rev}.gz')
        with gzip.open(path) as f:
            config = f.read()
        try:
            with open(rollback_config, 'wb') as f:
                f.write(config)
            copy(rollback_config, config_file)
        except OSError as e:
            raise ConfigMgmtError from e

        rc, out = rc_cmd('sudo systemctl reboot')
        if rc != 0:
            raise ConfigMgmtError(out)

        return msg, 0

    def rollback_soft(self, rev: int):
        """Rollback without reboot (rollback-soft)
        """
        msg = ''

        if not self._check_revision_number(rev):
            msg = f'Invalid revision number {rev}: must be 0 < rev < {self.num_revisions}'
            return msg, 1

        rollback_ct = self._get_config_tree_revision(rev)
        try:
            load(rollback_ct, switch='explicit')
            print('Rollback diff has been applied.')
            print('Use "compare" to review the changes or "commit" to apply them.')
        except LoadConfigError as e:
            raise ConfigMgmtError(e) from e

        return msg, 0

    def compare(self, saved: bool=False, commands: bool=False,
                rev1: Optional[int]=None,
                rev2: Optional[int]=None) -> Tuple[str,int]:
        """General compare function for config file revisions:
        revision n vs. revision m; working version vs. active version;
        or working version vs. saved version.
        """
        ct1 = self.active_config
        ct2 = self.working_config
        msg = 'No changes between working and active configurations.\n'
        if saved:
            ct1 = self._get_saved_config_tree()
            ct2 = self.working_config
            msg = 'No changes between working and saved configurations.\n'
        if rev1 is not None:
            if not self._check_revision_number(rev1):
                return f'Invalid revision number {rev1}', 1
            ct1 = self._get_config_tree_revision(rev1)
            ct2 = self.working_config
            msg = f'No changes between working and revision {rev1} configurations.\n'
        if rev2 is not None:
            if not self._check_revision_number(rev2):
                return f'Invalid revision number {rev2}', 1
            # compare older to newer
            ct2 = ct1
            ct1 = self._get_config_tree_revision(rev2)
            msg = f'No changes between revisions {rev2} and {rev1} configurations.\n'

        out = ''
        path = [] if commands else self.edit_path
        try:
            if commands:
                out = show_diff(ct1, ct2, path=path, commands=True)
            else:
                out = show_diff(ct1, ct2, path=path)
        except ConfigTreeError as e:
            return e, 1

        if out:
            msg = out

        return msg, 0

    def wrap_compare(self, options) -> Tuple[str,int]:
        """Interface to vyatta-cfg-run: args collected as 'options' to parse
        for compare.
        """
        cmnds = False
        r1 = None
        r2 = None
        if 'commands' in options:
            cmnds=True
            options.remove('commands')
        for i in options:
            if not i.isnumeric():
                options.remove(i)
        if len(options) > 0:
            r1 = int(options[0])
        if len(options) > 1:
            r2 = int(options[1])

        return self.compare(commands=cmnds, rev1=r1, rev2=r2)

    # Initialization and post-commit hooks for conf-mode
    #
    def initialize_revision(self):
        """Initialize config archive, logrotate conf, and commit log.
        """
        mask = os.umask(0o002)
        os.makedirs(archive_dir, exist_ok=True)
        json_dir = os.path.dirname(config_json)
        try:
            os.makedirs(json_dir, exist_ok=True)
            chown(json_dir, group='vyattacfg')
        except OSError as e:
            logger.warning(f'cannot create {json_dir}: {e}')

        self._add_logrotate_conf()

        if (not os.path.exists(commit_log_file) or
            self._get_number_of_revisions() == 0):
            user = self._get_user()
            via = 'init'
            comment = ''
            # add empty init config before boot-config load for revision
            # and diff consistency
            if self._archive_active_config():
                self._add_log_entry(user, via, comment)
                self._update_archive()

        os.umask(mask)

    def commit_revision(self):
        """Update commit log and rotate archived config.boot.

        commit_revision is called in post-commit-hooks, if
        ['commit-archive', 'commit-revisions'] is configured.
        """
        if os.getenv('IN_COMMIT_CONFIRM', ''):
            self._new_log_entry(tmp_file=tmp_log_entry)
            return

        if self._archive_active_config():
            self._add_log_entry()
            self._update_archive()

    def commit_archive(self):
        """Upload config to remote archive.
        """
        from vyos.remote import upload

        hostname = self.hostname
        t = datetime.now()
        timestamp = t.strftime('%Y%m%d_%H%M%S')
        remote_file = f'config.boot-{hostname}.{timestamp}'
        source_address = self.source_address

        if self.effective_locations:
            print("Archiving config...")
        for location in self.effective_locations:
            url = urlsplit(location)
            _, _, netloc = url.netloc.rpartition("@")
            redacted_location = urlunsplit(url._replace(netloc=netloc))
            print(f"  {redacted_location}", end=" ", flush=True)
            upload(archive_config_file, f'{location}/{remote_file}',
                   source_host=source_address)

    # op-mode functions
    #
    def get_raw_log_data(self) -> list:
        """Return list of dicts of log data:
           keys: [timestamp, user, commit_via, commit_comment]
        """
        log = self._get_log_entries()
        res_l = []
        for line in log:
            d = self._get_log_entry(line)
            res_l.append(d)

        return res_l

    @staticmethod
    def format_log_data(data: list) -> str:
        """Return formatted log data as str.
        """
        res_l = []
        for l_no, l in enumerate(data):
            time_d = datetime.fromtimestamp(int(l['timestamp']))
            time_str = time_d.strftime("%Y-%m-%d %H:%M:%S")

            res_l.append([l_no, time_str,
                          f"by {l['user']}", f"via {l['commit_via']}"])

            if l['commit_comment'] != 'commit': # default comment
                res_l.append([None, l['commit_comment']])

        ret = tabulate(res_l, tablefmt="plain")
        return ret

    @staticmethod
    def format_log_data_brief(data: list) -> str:
        """Return 'brief' form of log data as str.

        Slightly compacted format used in completion help for
        'rollback'.
        """
        res_l = []
        for l_no, l in enumerate(data):
            time_d = datetime.fromtimestamp(int(l['timestamp']))
            time_str = time_d.strftime("%Y-%m-%d %H:%M:%S")

            res_l.append(['\t', l_no, time_str,
                          f"{l['user']}", f"by {l['commit_via']}"])

        ret = tabulate(res_l, tablefmt="plain")
        return ret

    def show_commit_diff(self, rev: int, rev2: Optional[int]=None,
                         commands: bool=False) -> str:
        """Show commit diff at revision number, compared to previous
        revision, or to another revision.
        """
        if rev2 is None:
            out, _ = self.compare(commands=commands, rev1=rev, rev2=(rev+1))
            return out

        out, _ = self.compare(commands=commands, rev1=rev, rev2=rev2)
        return out

    def show_commit_file(self, rev: int) -> str:
        return self._get_file_revision(rev)

    # utility functions
    #

    def _get_saved_config_tree(self):
        with open(config_file) as f:
            c = f.read()
        return ConfigTree(c)

    def _get_file_revision(self, rev: int):
        if rev not in range(0, self._get_number_of_revisions()):
            raise ConfigMgmtError('revision not available')
        revision = os.path.join(archive_dir, f'config.boot.{rev}.gz')
        with gzip.open(revision) as f:
            r = f.read().decode()
        return r

    def _get_config_tree_revision(self, rev: int):
        c = self._get_file_revision(rev)
        return ConfigTree(c)

    def _add_logrotate_conf(self):
        conf: str = dedent(f"""\
        {archive_config_file} {{
            su root vyattacfg
            rotate {self.max_revisions}
            start 0
            compress
            copy
        }}
        """)
        conf_file = Path(logrotate_conf)
        conf_file.write_text(conf)
        conf_file.chmod(0o644)

    def _archive_active_config(self) -> bool:
        save_to_tmp = (boot_configuration_complete() or not
                       os.path.isfile(archive_config_file))
        mask = os.umask(0o113)

        ext = os.getpid()
        cmp_saved = f'/tmp/config.boot.{ext}'
        if save_to_tmp:
            save_config(cmp_saved, json_out=config_json)
        else:
            copy(config_file, cmp_saved)

        # on boot, we need to manually create the config.json file; after
        # boot, it is written by save_config, above
        if not os.path.exists(config_json):
            ct = self._get_saved_config_tree()
            try:
                with open(config_json, 'w') as f:
                    f.write(ct.to_json())
                chown(config_json, group='vyattacfg')
            except OSError as e:
                logger.warning(f'cannot create {config_json}: {e}')

        try:
            if cmp(cmp_saved, archive_config_file, shallow=False):
                os.unlink(cmp_saved)
                os.umask(mask)
                return False
        except FileNotFoundError:
            pass

        rc, out = rc_cmd(f'sudo mv {cmp_saved} {archive_config_file}')
        os.umask(mask)

        if rc != 0:
            logger.critical(f'mv file to archive failed: {out}')
            return False

        return True

    @staticmethod
    def _update_archive():
        cmd = f"sudo logrotate -f -s {logrotate_state} {logrotate_conf}"
        rc, out = rc_cmd(cmd)
        if rc != 0:
            logger.critical(f'logrotate failure: {out}')

    @staticmethod
    def _get_log_entries() -> list:
        """Return lines of commit log as list of strings
        """
        entries = []
        if os.path.exists(commit_log_file):
            with open(commit_log_file) as f:
                entries = f.readlines()

        return entries

    def _get_number_of_revisions(self) -> int:
        l = self._get_log_entries()
        return len(l)

    def _check_revision_number(self, rev: int) -> bool:
        self.num_revisions = self._get_number_of_revisions()
        if not 0 <= rev < self.num_revisions:
            return False
        return True

    @staticmethod
    def _get_user() -> str:
        import pwd

        try:
            user = os.getlogin()
        except OSError:
            try:
                user = pwd.getpwuid(os.geteuid())[0]
            except KeyError:
                user = 'unknown'
        return user

    def _new_log_entry(self, user: str='', commit_via: str='',
                       commit_comment: str='', timestamp: Optional[int]=None,
                       tmp_file: str=None) -> Optional[str]:
        # Format log entry and return str or write to file.
        #
        # Usage is within a post-commit hook, using env values. In case of
        # commit-confirm, it can be written to a temporary file for
        # inclusion on 'confirm'.
        from time import time

        if timestamp is None:
            timestamp = int(time())

        if not user:
            user = self._get_user()
        if not commit_via:
            commit_via = os.getenv('COMMIT_VIA', 'other')
        if not commit_comment:
            commit_comment = os.getenv('COMMIT_COMMENT', 'commit')

        # the commit log reserves '|' as field demarcation, so replace in
        # comment if present; undo this in _get_log_entry, below
        if re.search(r'\|', commit_comment):
            commit_comment = commit_comment.replace('|', '%%')

        entry = f'|{timestamp}|{user}|{commit_via}|{commit_comment}|\n'

        mask = os.umask(0o113)
        if tmp_file is not None:
            try:
                with open(tmp_file, 'w') as f:
                    f.write(entry)
            except OSError as e:
                logger.critical(f'write to {tmp_file} failed: {e}')
            os.umask(mask)
            return None

        os.umask(mask)
        return entry

    @staticmethod
    def _get_log_entry(line: str) -> dict:
        log_fmt = re.compile(r'\|.*\|\n?$')
        keys = ['user', 'commit_via', 'commit_comment', 'timestamp']
        if not log_fmt.match(line):
            logger.critical(f'Invalid log format {line}')
            return {}

        timestamp, user, commit_via, commit_comment = (
        tuple(line.strip().strip('|').split('|')))

        commit_comment = commit_comment.replace('%%', '|')
        d = dict(zip(keys, [user, commit_via,
                            commit_comment, timestamp]))

        return d

    def _read_tmp_log_entry(self) -> dict:
        try:
            with open(tmp_log_entry) as f:
                entry = f.read()
            os.unlink(tmp_log_entry)
        except OSError as e:
            logger.critical(f'error on file {tmp_log_entry}: {e}')

        return self._get_log_entry(entry)

    def _add_log_entry(self, user: str='', commit_via: str='',
                       commit_comment: str='', timestamp: Optional[int]=None):
        mask = os.umask(0o113)

        entry = self._new_log_entry(user=user, commit_via=commit_via,
                                    commit_comment=commit_comment,
                                    timestamp=timestamp)

        log_entries = self._get_log_entries()
        log_entries.insert(0, entry)
        if len(log_entries) > self.max_revisions:
            log_entries = log_entries[:-1]

        try:
            with open(commit_log_file, 'w') as f:
                f.writelines(log_entries)
        except OSError as e:
            logger.critical(e)

        os.umask(mask)

# entry_point for console script
#
def run():
    from argparse import ArgumentParser, REMAINDER

    config_mgmt = ConfigMgmt()

    for s in list(commit_hooks):
        if sys.argv[0].replace('-', '_').endswith(s):
            func = getattr(config_mgmt, s)
            try:
                func()
            except Exception as e:
                print(f'{s}: {e}')
            sys.exit(0)

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='subcommand')

    commit_confirm = subparsers.add_parser('commit_confirm',
                     help="Commit with opt-out reboot to saved config")
    commit_confirm.add_argument('-t', dest='minutes', type=int,
                                default=DEFAULT_TIME_MINUTES,
                                help="Minutes until reboot, unless 'confirm'")
    commit_confirm.add_argument('-y', dest='no_prompt', action='store_true',
                                help="Execute without prompt")

    subparsers.add_parser('confirm', help="Confirm commit")
    subparsers.add_parser('revert', help="Revert commit-confirm")

    rollback = subparsers.add_parser('rollback',
                                     help="Rollback to earlier config")
    rollback.add_argument('--rev', type=int,
                          help="Revision number for rollback")
    rollback.add_argument('-y', dest='no_prompt', action='store_true',
                          help="Excute without prompt")

    rollback_soft = subparsers.add_parser('rollback_soft',
                                     help="Rollback to earlier config")
    rollback_soft.add_argument('--rev', type=int,
                          help="Revision number for rollback")

    compare = subparsers.add_parser('compare',
                                    help="Compare config files")

    compare.add_argument('--saved', action='store_true',
                         help="Compare session config with saved config")
    compare.add_argument('--commands', action='store_true',
                         help="Show difference between commands")
    compare.add_argument('--rev1', type=int, default=None,
                         help="Compare revision with session config or other revision")
    compare.add_argument('--rev2', type=int, default=None,
                         help="Compare revisions")

    wrap_compare = subparsers.add_parser('wrap_compare',
                                         help="Wrapper interface for vyatta-cfg-run")
    wrap_compare.add_argument('--options', nargs=REMAINDER)

    args = vars(parser.parse_args())

    func = getattr(config_mgmt, args['subcommand'])
    del args['subcommand']

    res = ''
    try:
        res, rc = func(**args)
    except ConfigMgmtError as e:
        print(e)
        sys.exit(1)
    if res:
        print(res)
    sys.exit(rc)
