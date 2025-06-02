# Copyright (C) 2021-2024 VyOS maintainers and contributors
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
import unittest
import paramiko
import pprint

from time import sleep
from typing import Type

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos import ConfigError
from vyos.defaults import commit_lock
from vyos.utils.process import cmd
from vyos.utils.process import run

save_config = '/tmp/vyos-smoketest-save'

# The commit process is not finished until all pending files from
# VYATTA_CHANGES_ONLY_DIR are copied to VYATTA_ACTIVE_CONFIGURATION_DIR. This
# is done inside libvyatta-cfg1 and the FUSE UnionFS part. On large non-
# interactive commits FUSE UnionFS might not replicate the real state in time,
# leading to errors when querying the working and effective configuration.
# TO BE DELETED AFTER SWITCH TO IN MEMORY CONFIG
CSTORE_GUARD_TIME = 4

# This class acts as shim between individual Smoketests developed for VyOS and
# the Python UnitTest framework. Before every test is loaded, we dump the current
# system configuration and reload it after the test - despite the test results.
#
# Using this approach we can not render a live system useless while running any
# kind of smoketest. In addition it adds debug capabilities like printing the
# command used to execute the test.
class VyOSUnitTestSHIM:
    class TestCase(unittest.TestCase):
        # if enabled in derived class, print out each and every set/del command
        # on the CLI. This is usefull to grap all the commands required to
        # trigger the certain failure condition.
        # Use "self.debug = True" in derived classes setUp() method
        debug = False
        # Time to wait after a commit to ensure the CStore is up to date
        # only required for testcases using FRR
        _commit_guard_time = 0
        @classmethod
        def setUpClass(cls):
            cls._session = ConfigSession(os.getpid())
            cls._session.save_config(save_config)
            if os.path.exists('/tmp/vyos.smoketest.debug'):
                cls.debug = True
            pass

        @classmethod
        def tearDownClass(cls):
            # discard any pending changes which might caused a messed up config
            cls._session.discard()
            # ... and restore the initial state
            cls._session.migrate_and_load_config(save_config)

            try:
                cls._session.commit()
            except (ConfigError, ConfigSessionError):
                cls._session.discard()
                cls.fail(cls)

        def cli_set(self, path, value=None):
            if self.debug:
                str = f'set {" ".join(path)} {value}' if value else f'set {" ".join(path)}'
                print(str)
            self._session.set(path, value)

        def cli_delete(self, config):
            if self.debug:
                print('del ' + ' '.join(config))
            self._session.delete(config)

        def cli_discard(self):
            if self.debug:
                print('DISCARD')
            self._session.discard()

        def cli_commit(self):
            if self.debug:
                print('commit')
            # During a commit there is a process opening commit_lock, and run()
            # returns 0
            while run(f'sudo lsof -nP {commit_lock}') == 0:
                sleep(0.250)
            # Return the output of commit
            # Necessary for testing Warning cases
            out = self._session.commit()
            # Wait for CStore completion for fast non-interactive commits
            sleep(self._commit_guard_time)

            return out

        def op_mode(self, path : list) -> None:
            """
            Execute OP-mode command and return stdout
            """
            if self.debug:
                print('commit')
            path = ' '.join(path)
            out = cmd(f'/opt/vyatta/bin/vyatta-op-cmd-wrapper {path}')
            if self.debug:
                print(f'\n\ncommand "{path}" returned:\n')
                pprint.pprint(out)
            return out

        def getFRRconfig(self, string=None, end='$', endsection='^!',
                         substring=None, endsubsection=None, empty_retry=0):
            """
            Retrieve current "running configuration" from FRR

            string:        search for a specific start string in the configuration
            end:           end of the section to search for (line ending)
            endsection:    end of the configuration
            substring:     search section under the result found by string
            endsubsection: end of the subsection (usually something with "exit")
            """
            command = f'vtysh -c "show run no-header"'
            if string:
                command += f' | sed -n "/^{string}{end}/,/{endsection}/p"'
                if substring and endsubsection:
                    command += f' | sed -n "/^{substring}/,/{endsubsection}/p"'
            out = cmd(command)
            if self.debug:
                print(f'\n\ncommand "{command}" returned:\n')
                pprint.pprint(out)
            if empty_retry > 0:
                retry_count = 0
                while not out and retry_count < empty_retry:
                    if self.debug and retry_count % 10 == 0:
                        print(f"Attempt {retry_count}: FRR config is still empty. Retrying...")
                    retry_count += 1
                    sleep(1)
                    out = cmd(command)
                if not out:
                    print(f'FRR configuration still empty after {empty_retry} retires!')
            return out

        @staticmethod
        def ssh_send_cmd(command, username, password, key_filename=None,
                         hostname='localhost'):
            """ SSH command execution helper """
            # Try to login via SSH
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(hostname=hostname, username=username,
                               password=password, key_filename=key_filename)
            _, stdout, stderr = ssh_client.exec_command(command)
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            ssh_client.close()
            return output, error

        # Verify nftables output
        def verify_nftables(self, nftables_search, table, inverse=False, args=''):
            nftables_output = cmd(f'sudo nft {args} list table {table}')

            for search in nftables_search:
                matched = False
                for line in nftables_output.split("\n"):
                    if all(item in line for item in search):
                        matched = True
                        break
                self.assertTrue(not matched if inverse else matched, msg=search)

        def verify_nftables_chain(self, nftables_search, table, chain, inverse=False, args=''):
            nftables_output = cmd(f'sudo nft {args} list chain {table} {chain}')

            for search in nftables_search:
                matched = False
                for line in nftables_output.split("\n"):
                    if all(item in line for item in search):
                        matched = True
                        break
                self.assertTrue(not matched if inverse else matched, msg=search)

        def verify_nftables_chain_exists(self, table, chain, inverse=False):
            try:
                cmd(f'sudo nft list chain {table} {chain}')
                if inverse:
                    self.fail(f'Chain exists: {table} {chain}')
            except OSError:
                if not inverse:
                    self.fail(f'Chain does not exist: {table} {chain}')

        # Verify ip rule output
        def verify_rules(self, rules_search, inverse=False, addr_family='inet'):
            rule_output = cmd(f'ip -family {addr_family} rule show')

            for search in rules_search:
                matched = False
                for line in rule_output.split("\n"):
                    if all(item in line for item in search):
                        matched = True
                        break
                self.assertTrue(not matched if inverse else matched, msg=search)

# standard construction; typing suggestion: https://stackoverflow.com/a/70292317
def ignore_warning(warning: Type[Warning]):
    import warnings
    from functools import wraps

    def inner(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=warning)
                return f(*args, **kwargs)
        return wrapped
    return inner
