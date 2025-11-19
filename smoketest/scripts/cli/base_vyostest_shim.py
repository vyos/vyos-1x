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
import paramiko
import pprint
import re
import unittest

from time import sleep
from typing import Type

from vyos import ConfigError
from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.defaults import commit_lock
from vyos.frrender import mgmt_daemon
from vyos.utils.process import cmd
from vyos.utils.process import process_named_running
from vyos.utils.process import run

save_config = '/tmp/vyos-smoketest-save'

# This class acts as shim between individual Smoketests developed for VyOS and
# the Python UnitTest framework. Before every test is loaded, we dump the current
# system configuration and reload it after the test - despite the test results.
#
# Using this approach we can not render a live system useless while running any
# kind of smoketest. In addition it adds debug capabilities like printing the
# command used to execute the test.

class VyOSUnitTestSHIM:
    class TestCase(unittest.TestCase):
        # If enabled, print out each and every set/del command on stdout.
        # This is usefull to grap all the commands required to trigger the
        # certain failure condition.
        debug = False
        mgmt_daemon_pid = 0

        @staticmethod
        def debug_on():
            return os.path.exists('/tmp/vyos.smoketest.debug')

        @classmethod
        def setUpClass(cls):
            cls._session = ConfigSession(os.getpid())
            cls._session.save_config(save_config)
            cls.debug = cls.debug_on()

            # Retrieve FRR mgmtd daemon PID - it is not allowed to crash, thus
            # PID must remain the same
            cls.mgmt_daemon_pid = process_named_running(mgmt_daemon)

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

        def setUp(self):
            pass

        def tearDown(self):
            # check process health and continuity
            self.assertEqual(self.mgmt_daemon_pid, process_named_running(mgmt_daemon))

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
            return self._session.commit()

        def cli_save(self, file):
            if self.debug:
                print('save')
            self._session.save_config(file)

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

        def getFRRconfig(self, start_section:str=None, end_marker='$', stop_section='^!',
                         start_subsection:str=None, stop_subsection='^ exit') -> str:
            """
            Retrieve current "running configuration" from FRR

            start_section:    search for a specific start string in the configuration
            end_marker:       override default "line end $" marker to match on an
                              "open end" string
            stop_section:     end of the configuration
            start_subsection: search section under the result found by string
            stop_subsection:  end of the subsection (usually something with "exit")
            """
            from vyos.utils.process import rc_cmd

            rc, frr_config = rc_cmd('vtysh -c "show running-config no-header"')
            self.assertEqual(rc, 0)

            if not start_section:
                return frr_config

            extracted = []
            in_section = False
            for line in frr_config.splitlines():
                if not in_section:
                    if re.match(f'^{start_section}{end_marker}', line):
                        in_section = True
                        extracted.append(line)
                else:
                    extracted.append(line)
                    if re.match(stop_section, line):
                        break
            output = '\n'.join(extracted)

            # Use extracted list when searching for optional subsection
            # used by e.g. BGP address-family check
            if start_subsection:
                extracted_subsection = []
                in_subsection = False
                for line in extracted:
                    if not in_subsection:
                        if re.match(start_subsection, line):
                            in_subsection = True
                            extracted_subsection.append(line)
                    else:
                        extracted_subsection.append(line)
                        if re.match(stop_subsection, line):
                            break
                output = '\n'.join(extracted_subsection)

            if self.debug:
                print(output)
            return output

        def getFRRopmode(self, command : str, json : bool=False):
            from json import loads
            if json: command += f' json'
            out = cmd(f'vtysh -c "{command}"')
            if json:
                out = loads(out)
            if self.debug:
                print(f'\n\ncommand "{command}" returned:\n')
                pprint.pprint(out)
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
        def verify_nftables(self, nftables_search: list[list[str]], table: str, inverse: bool=False, args: str='') -> None:
            """
            Assert presence or absence of lines in `nft list table` output.

            This helper inspects the output of `sudo nft {args} list table {table}`
            and, for each entry in `nftables_search`, checks whether there exists
            a single line that contains all specified substrings.

            #### Usage:
                nftables output excerpt:
                    ```text
                    chain VYOS_STATE_POLICY {
                            ct state established counter packets 0 bytes 0 accept
                            ct state invalid counter packets 0 bytes 0 drop
                            ct state related counter packets 0 bytes 0 accept
                    }
                    ```

            ##### Example 1:
                Verify that the chain VYOS_STATE_POLICY exists and contains the specified fragments

                Code usage:
                    ```python
                    nftables_search = [
                        ["chain VYOS_STATE_POLICY"],
                        ["ct state established", "accept"],
                    ]
                    self.verify_nftables(nftables_search, "ip vyos_filter")
                    ```

            ##### Example 2 (inverse matching):
                Verify that the ct state established does not have a verdict of drop

                Code usage:
                    ```python
                    nftables_search = [
                        ["ct state established", "drop"]
                    ]
                    self.verify_nftables(nftables_search, "ip vyos_filter", inverse=True)
                    ```

            Parameters:
                nftables_search: list[list[str]]
                    A list of search groups. Each inner list contains substrings
                    that must all appear within the same output line to count as
                    a match.
                table: str
                        Table spec accepted by nft (e.g. "ip vyos_filter" or
                        "ip6 vyos_filter").
                inverse: bool
                    If True, assert that no output line matches any search group.
                    If False, assert that each search group is matched at least once.
                args: str
                    Extra flags for `nft` (e.g. "-a" to show rule handles or "-s" to omit counter hits).

            Raises:
                AssertionError: If expectations are not met.
            """
            nftables_output = cmd(f'sudo nft {args} list table {table}')

            for search in nftables_search:
                matched = False
                for line in nftables_output.split("\n"):
                    if all(item in line for item in search):
                        matched = True
                        break
                self.assertTrue(not matched if inverse else matched, msg=search)

        def verify_nftables_chain(self, nftables_search: list[list[str]], table: str, chain: str, inverse: bool=False, args: str='') -> None:
            """
            Assert presence or absence of lines in `nft list chain` output.

            This behaves like `verify_nftables` but focuses on a specific chain within a table using
            `sudo nft {args} list chain {table} {chain}`. For each entry in `nftables_search`, it
            checks whether there exists a single line that contains all specified substrings.

            #### Usage:
                nftables output excerpt:
                    ```text
                    chain VYOS_INPUT_filter {
                            tcp dport 22 counter packets 0 bytes 0 accept
                            tcp dport 23 counter packets 0 bytes 0 drop
                    }
                    ```

            ##### Example 1:
                Verify the chain contains the specified fragments

                Code usage:
                    ```python
                    nftables_search = [
                        ["tcp dport 22", "accept"],
                        ["tcp dport 23", "drop"]
                    ]
                    self.verify_nftables_chain(
                        nftables_search, table="ip vyos_filter", chain="VYOS_INPUT_filter"
                    )
                    ```

            ##### Example 2 (inverse matching):
                Verify that a drop rule for tcp dport 22 is not present

                Code usage:
                    ```python
                    nftables_search = [
                        ["tcp dport 22", "drop"]
                    ]
                    self.verify_nftables_chain(
                        nftables_search, table="ip vyos_filter", chain="VYOS_INPUT_filter", inverse=True
                    )
                    ```

            Parameters:
                nftables_search: list[list[str]]
                    A list of search groups. Each inner list contains substrings
                    that must all appear within the same output line to count as
                    a match.
                table: str
                        Table spec accepted by nft (e.g. "ip vyos_filter" or
                        "ip6 vyos_filter").
                chain: str
                    Chain name within the specified table.
                inverse: bool
                    If True, assert that no output line matches any search group.
                    If False, assert that each search group is matched at least once.
                args: str
                    Extra flags for `nft` (e.g. "-a" to show rule handles or "-s" to omit counter hits).

            Raises:
                AssertionError: If expectations are not met.
            """
            nftables_output = cmd(f'sudo nft {args} list chain {table} {chain}')

            for search in nftables_search:
                matched = False
                for line in nftables_output.split("\n"):
                    if all(item in line for item in search):
                        matched = True
                        break
                self.assertTrue(not matched if inverse else matched, msg=search)

        def verify_nftables_chain_exists(self, table: str, chain: str, inverse: bool=False) -> None:
            """
            Assert existence or non-existence of an nftables chain.

            Calls `sudo nft list chain {table} {chain}` and verifies whether the
            chain does or does not exist.

            Usage:
                nftables output excerpt:
                    ```text
                    chain VYOS_INPUT_filter {
                            ct state established accept
                    }
                    ```

            ##### Example 1:
                Verify a chain exists

                Code usage:
                    ```python
                    self.verify_nftables_chain_exists(
                        table="ip vyos_filter", chain="VYOS_INPUT_filter"
                    )
                    ```

            ##### Example 2 (inverse matching):
                Verify a deprecated chain is not present

                Code usage:
                    ```python
                    self.verify_nftables_chain_exists(
                        table="ip VYOS_INPUT_filter", chain="deprecated_chain", inverse=True
                    )
                    ```

            Parameters:
                table: str
                    Table spec accepted by nft (e.g. "ip vyos_filter" or
                    "ip6 vyos_filter").
                chain: str
                    Chain name within the specified table.
                inverse: bool
                    If True, assert the chain does not exist. If False, assert it exists.

            Raises:
                AssertionError: If expectations are not met.
            """
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
