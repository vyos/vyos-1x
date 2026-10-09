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

import re

from base_vyostest_shim import VyOSUnitTestSHIM
from configparser import ConfigParser

from vyos.configsession import ConfigSessionError
from vyos.template import is_ipv4
from vyos.utils.cpu import get_core_count
from vyos.utils.process import process_named_running
from vyos.utils.process import cmdl


class BasicAccelPPPTest:
    class TestCase(VyOSUnitTestSHIM.TestCase):
        _base_path = None
        _config_file = None
        _chap_secrets = None
        _protocol_section = None
        # Authentication mode set by initial_auth_config()
        _auth_mode = 'local'
        # Server negotiates PPP and thus supports ppp-options, auth protocols, ...
        _ppp = True

        @classmethod
        def setUpClass(cls):
            cls._process_name = "accel-pppd"

            super(BasicAccelPPPTest.TestCase, cls).setUpClass()

            # ensure we can also run this test on a live system - so lets clean
            # out the current configuration :)
            cls.cli_delete(cls, cls._base_path)

        def setUp(self):
            self._gateway = "192.0.2.1"
            # ensure we can also run this test on a live system - so lets clean
            # out the current configuration :)
            self.cli_delete(self._base_path)
            # always forward to base class
            super().setUp()

        def tearDown(self):
            # Check for running process
            self.assertTrue(process_named_running(self._process_name))

            self.cli_delete(self._base_path)
            self.cli_commit()

            # Check for running process
            self.assertFalse(process_named_running(self._process_name))
            # always forward to base class
            super().tearDown()

        def _accel_pid(self):
            return process_named_running(self._process_name, cmdline=self._config_file)

        def cli_commit(self):
            # Accel-PPP-NG re-reads its configuration without dropping
            # sessions, only deleting and re-creating the service may
            # spawn a new daemon
            pid_before = self._accel_pid()
            out = super().cli_commit()
            pid_after = self._accel_pid()
            if pid_before and pid_after:
                self.assertEqual(pid_before, pid_after,
                                 msg=f'{self._process_name} PID changed on reconfiguration')
            return out

        def set(self, path):
            self.cli_set(self._base_path + path)

        def delete(self, path):
            self.cli_delete(self._base_path + path)

        def basic_protocol_specific_config(self):
            """
            An astract method.
            Initialize protocol specific configurations.
            """
            self.assertFalse(True, msg="Function must be defined")

        def initial_auth_config(self):
            """
            Initialization of default authentication for all protocols
            """
            self.set(
                [
                    "authentication",
                    "local-users",
                    "username",
                    "vyos",
                    "password",
                    "vyos",
                ]
            )
            self.set(["authentication", "mode", "local"])

        def initial_gateway_config(self):
            """
            Initialization of default gateway
            """
            self.set(["gateway-address", self._gateway])

        def initial_pool_config(self):
            """
            Initialization of default client ip pool
            """
            first_pool = "SIMPLE-POOL"
            self.set(["client-ip-pool", first_pool, "range", "192.0.2.0/24"])
            self.set(["default-pool", first_pool])

        def basic_config(self, is_auth=True, is_gateway=True, is_client_pool=True):
            """
            Initialization of basic configuration
            :param is_auth: authentication initialization
            :type is_auth: bool
            :param is_gateway: gateway initialization
            :type is_gateway: bool
            :param is_client_pool: client ip pool initialization
            :type is_client_pool: bool
            """
            self.basic_protocol_specific_config()
            if is_auth:
                self.initial_auth_config()
            if is_gateway:
                self.initial_gateway_config()
            if is_client_pool:
                self.initial_pool_config()

        def getConfig(self, start, end="cli"):
            """
            Return part of configuration from line
            where the first injection of start keyword to the line
            where the first injection of end keyword
            :param start: start keyword
            :type start: str
            :param end: end keyword
            :type end: str
            :return: part of config
            :rtype: str
            """
            start_pattern = f'[{start}'
            end_pattern = f'[{end}'
            with open(self._config_file) as f:
                lines = f.read().splitlines()

            matched = []
            in_range = False
            for line in lines:
                if not in_range:
                    if line.startswith(start_pattern):
                        in_range = True
                        matched.append(line)
                else:
                    matched.append(line)
                    if line.startswith(end_pattern):
                        break

            return '\n'.join(matched)

        def verify(self, conf):
            self.assertEqual(conf["core"]["thread-count"], str(get_core_count()))

        def test_accel_name_servers(self):
            # Verify proper Name-Server configuration for IPv4 and IPv6
            self.basic_config()

            nameserver = ["192.0.2.1", "192.0.2.2", "2001:db8::1"]
            for ns in nameserver:
                self.set(["name-server", ns])

            # commit changes
            self.cli_commit()

            # Validate configuration values
            conf = ConfigParser(allow_no_value=True, delimiters="=", strict=False)
            conf.read(self._config_file)

            # IPv4 and IPv6 nameservers must be checked individually
            for ns in nameserver:
                if is_ipv4(ns):
                    self.assertIn(ns, [conf["dns"]["dns1"], conf["dns"]["dns2"]])
                else:
                    self.assertEqual(conf["ipv6-dns"][ns], None)

        def test_accel_local_authentication(self):
            # Test configuration of local authentication
            self.basic_config()

            # upload / download limit
            user = "test"
            password = "test2"
            static_ip = "100.100.100.101"
            upload = "5000"
            download = "10000"
            self.set(
                [
                    "authentication",
                    "local-users",
                    "username",
                    user,
                    "password",
                    password,
                ]
            )
            self.set(
                [
                    "authentication",
                    "local-users",
                    "username",
                    user,
                    "static-ip",
                    static_ip,
                ]
            )
            self.set(
                [
                    "authentication",
                    "local-users",
                    "username",
                    user,
                    "rate-limit",
                    "upload",
                    upload,
                ]
            )

            # upload rate-limit requires also download rate-limit
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.set(
                [
                    "authentication",
                    "local-users",
                    "username",
                    user,
                    "rate-limit",
                    "download",
                    download,
                ]
            )

            # commit changes
            self.cli_commit()

            # Validate configuration values
            conf = ConfigParser(allow_no_value=True, delimiters="=", strict=False)
            conf.read(self._config_file)

            # check proper path to chap-secrets file
            self.assertEqual(conf["chap-secrets"]["chap-secrets"], self._chap_secrets)

            # basic verification
            self.verify(conf)

            # check local users
            tmp = cmdl(['cat', self._chap_secrets], sudo=True)
            regex = f"{user}\s+\*\s+{password}\s+{static_ip}\s+{download}/{upload}"
            tmp = re.findall(regex, tmp)
            self.assertTrue(tmp)

            # Check local-users default value(s)
            self.delete(
                ["authentication", "local-users", "username", user, "static-ip"]
            )
            # commit changes
            self.cli_commit()

            # check local users
            tmp = cmdl(['cat', self._chap_secrets], sudo=True)
            regex = f"{user}\s+\*\s+{password}\s+\*\s+{download}/{upload}"
            tmp = re.findall(regex, tmp)
            self.assertTrue(tmp)

        def test_accel_radius_authentication(self):
            # Test configuration of RADIUS authentication for PPPoE server
            self.basic_config()

            radius_server = "192.0.2.22"
            radius_key = "secretVyOS"
            radius_port = "2000"
            radius_port_acc = "3000"
            acct_interim_jitter = '10'
            acct_interim_interval = '10'
            acct_timeout = '30'

            self.set(["authentication", "mode", "radius"])
            self.set(
                ["authentication", "radius", "server", radius_server, "key", radius_key]
            )
            self.set(
                [
                    "authentication",
                    "radius",
                    "server",
                    radius_server,
                    "port",
                    radius_port,
                ]
            )
            self.set(
                [
                    "authentication",
                    "radius",
                    "server",
                    radius_server,
                    "acct-port",
                    radius_port_acc,
                ]
            )
            self.set(
                [
                    "authentication",
                    "radius",
                    "acct-interim-jitter",
                    acct_interim_jitter,
                ]
            )
            self.set(
                [
                    "authentication",
                    "radius",
                    "accounting-interim-interval",
                    acct_interim_interval,
                ]
            )
            self.set(
                [
                    "authentication",
                    "radius",
                    "acct-timeout",
                    acct_timeout,
                ]
            )

            coa_server = "4.4.4.4"
            coa_key = "testCoA"
            self.set(
                ["authentication", "radius", "dynamic-author", "server", coa_server]
            )
            self.set(["authentication", "radius", "dynamic-author", "key", coa_key])

            nas_id = "VyOS-PPPoE"
            nas_ip = "7.7.7.7"
            self.set(["authentication", "radius", "nas-identifier", nas_id])
            self.set(["authentication", "radius", "nas-ip-address", nas_ip])

            source_address = "1.2.3.4"
            self.set(["authentication", "radius", "source-address", source_address])

            self.set(
                [
                    "authentication",
                    "radius",
                    "message-authenticator",
                    "include-access-request",
                ]
            )
            self.set(
                [
                    "authentication",
                    "radius",
                    "message-authenticator",
                    "require-access-response",
                ]
            )

            # commit changes
            self.cli_commit()

            # Validate configuration values
            conf = ConfigParser(allow_no_value=True, delimiters="=", strict=False)
            conf.read(self._config_file)

            # basic verification
            self.verify(conf)

            # check auth
            self.assertTrue(conf["radius"].getboolean("verbose"))
            self.assertEqual(conf["radius"]["acct-timeout"], acct_timeout)
            self.assertEqual(
                conf["radius"]["acct-interim-interval"], acct_interim_interval
            )
            self.assertEqual(conf["radius"]["acct-interim-jitter"], acct_interim_jitter)
            self.assertEqual(conf["radius"]["timeout"], "3")
            self.assertEqual(conf["radius"]["max-try"], "3")

            self.assertEqual(
                conf["radius"]["dae-server"], f"{coa_server}:1700,{coa_key}"
            )
            self.assertEqual(conf["radius"]["nas-identifier"], nas_id)
            self.assertEqual(conf["radius"]["nas-ip-address"], nas_ip)
            self.assertEqual(conf["radius"]["bind"], source_address)
            self.assertEqual(
                conf["radius"]["message-authenticator-include-access-request"], "1"
            )
            self.assertEqual(
                conf["radius"]["message-authenticator-require-access-response"], "1"
            )

            server = conf["radius"]["server"].split(",")
            self.assertEqual(radius_server, server[0])
            self.assertEqual(radius_key, server[1])
            self.assertEqual(f"auth-port={radius_port}", server[2])
            self.assertEqual(f"acct-port={radius_port_acc}", server[3])
            self.assertEqual(f"req-limit=0", server[4])
            self.assertEqual(f"fail-time=0", server[5])

            #
            # Disable Radius Accounting
            #
            self.delete(
                ["authentication", "radius", "server", radius_server, "acct-port"]
            )
            self.set(
                [
                    "authentication",
                    "radius",
                    "server",
                    radius_server,
                    "disable-accounting",
                ]
            )

            self.set(
                [
                    "authentication",
                    "radius",
                    "server",
                    radius_server,
                    "backup",
                ]
            )

            self.set(
                [
                    "authentication",
                    "radius",
                    "server",
                    radius_server,
                    "priority",
                    "10",
                ]
            )

            # commit changes
            self.cli_commit()

            conf.read(self._config_file)

            server = conf["radius"]["server"].split(",")
            self.assertEqual(radius_server, server[0])
            self.assertEqual(radius_key, server[1])
            self.assertEqual(f"auth-port={radius_port}", server[2])
            self.assertEqual(f"acct-port=0", server[3])
            self.assertEqual(f"req-limit=0", server[4])
            self.assertEqual(f"fail-time=0", server[5])
            self.assertIn('weight=10', server)
            self.assertIn('backup', server)

        def test_accel_ipv4_pool(self):
            self.basic_config(is_gateway=False, is_client_pool=False)
            gateway = "192.0.2.1"
            subnet = "172.16.0.0/24"
            first_pool = "POOL1"
            second_pool = "POOL2"
            range = "192.0.2.10-192.0.2.20"
            range_config = "192.0.2.10-20"

            self.set(["gateway-address", gateway])
            self.set(["client-ip-pool", first_pool, "range", subnet])
            self.set(["client-ip-pool", first_pool, "next-pool", second_pool])
            self.set(["client-ip-pool", second_pool, "range", range])
            self.set(["default-pool", first_pool])
            # commit changes

            self.cli_commit()

            # Validate configuration values
            conf = ConfigParser(allow_no_value=True, delimiters="=", strict=False)
            conf.read(self._config_file)

            self.assertEqual(
                f"{first_pool},next={second_pool}", conf["ip-pool"][f"{subnet},name"]
            )
            self.assertEqual(second_pool, conf["ip-pool"][f"{range_config},name"])
            self.assertEqual(gateway, conf["ip-pool"]["gw-ip-address"])
            self.assertEqual(first_pool, conf[self._protocol_section]["ip-pool"])

        def test_accel_next_pool(self):
            # T5099 required specific order
            self.basic_config(is_gateway=False, is_client_pool=False)

            gateway = "192.0.2.1"
            first_pool = "VyOS-pool1"
            first_subnet = "192.0.2.0/25"
            second_pool = "Vyos-pool2"
            second_subnet = "203.0.113.0/25"
            third_pool = "Vyos-pool3"
            third_subnet = "198.51.100.0/24"

            self.set(["gateway-address", gateway])
            self.set(["client-ip-pool", first_pool, "range", first_subnet])
            self.set(["client-ip-pool", first_pool, "next-pool", second_pool])
            self.set(["client-ip-pool", second_pool, "range", second_subnet])
            self.set(["client-ip-pool", second_pool, "next-pool", third_pool])
            self.set(["client-ip-pool", third_pool, "range", third_subnet])

            # commit changes
            self.cli_commit()

            config = self.getConfig("ip-pool")

            pool_config = f"""gw-ip-address={gateway}
{third_subnet},name={third_pool}
{second_subnet},name={second_pool},next={third_pool}
{first_subnet},name={first_pool},next={second_pool}"""
            self.assertIn(pool_config, config)

        def test_accel_ipv6_pool(self):
            # Test configuration of IPv6 client pools
            self.basic_config(is_gateway=False, is_client_pool=False)

            # Enable IPv6
            allow_ipv6 = 'allow'
            self.set(['ppp-options', 'ipv6', allow_ipv6])

            pool_name = 'ipv6_test_pool'
            prefix_1 = '2001:db8:fffe::/56'
            prefix_mask = '64'
            prefix_2 = '2001:db8:ffff::/56'
            client_prefix_1 = f'{prefix_1},{prefix_mask}'
            client_prefix_2 = f'{prefix_2},{prefix_mask}'
            self.set(
                ['client-ipv6-pool', pool_name, 'prefix', prefix_1, 'mask', prefix_mask]
            )
            self.set(
                ['client-ipv6-pool', pool_name, 'prefix', prefix_2, 'mask', prefix_mask]
            )

            delegate_1_prefix = '2001:db8:fff1::/56'
            delegate_2_prefix = '2001:db8:fff2::/56'
            delegate_mask = '64'
            self.set(
                [
                    'client-ipv6-pool',
                    pool_name,
                    'delegate',
                    delegate_1_prefix,
                    'delegation-prefix',
                    delegate_mask,
                ]
            )
            self.set(
                [
                    'client-ipv6-pool',
                    pool_name,
                    'delegate',
                    delegate_2_prefix,
                    'delegation-prefix',
                    delegate_mask,
                ]
            )

            # commit changes
            self.cli_commit()

            # Validate configuration values
            conf = ConfigParser(allow_no_value=True, delimiters='=', strict=False)
            conf.read(self._config_file)

            for tmp in ['ipv6pool', 'ipv6_nd', 'ipv6_dhcp']:
                self.assertEqual(conf['modules'][tmp], None)

            self.assertEqual(conf['ppp']['ipv6'], allow_ipv6)

            config = self.getConfig("ipv6-pool")
            pool_config = f"""{client_prefix_1},name={pool_name}
{client_prefix_2},name={pool_name}
delegate={delegate_1_prefix},{delegate_mask},name={pool_name}
delegate={delegate_2_prefix},{delegate_mask},name={pool_name}"""
            self.assertIn(pool_config, config)

        def test_accel_ppp_options(self):
            # Test configuration of local authentication for PPPoE server
            self.basic_config()

            # other settings
            mppe = 'require'
            self.set(['ppp-options', 'disable-ccp'])
            self.set(['ppp-options', 'mppe', mppe])

            # min-mtu
            min_mtu = '1400'
            self.set(['ppp-options', 'min-mtu', min_mtu])

            # mru
            mru = '9000'
            self.set(['ppp-options', 'mru', mru])

            # interface-cache
            interface_cache = '128000'
            self.set(['ppp-options', 'interface-cache', interface_cache])

            # ipv6
            allow_ipv6 = 'allow'
            allow_ipv4 = 'require'
            random = 'random'
            lcp_failure = '4'
            lcp_interval = '40'
            lcp_timeout = '100'
            self.set(['ppp-options', 'ipv4', allow_ipv4])
            self.set(['ppp-options', 'ipv6', allow_ipv6])
            self.set(['ppp-options', 'ipv6-interface-id', random])
            self.set(['ppp-options', 'ipv6-accept-peer-interface-id'])
            self.set(['ppp-options', 'ipv6-peer-interface-id', random])
            self.set(['ppp-options', 'lcp-echo-failure', lcp_failure])
            self.set(['ppp-options', 'lcp-echo-interval', lcp_interval])
            self.set(['ppp-options', 'lcp-echo-timeout', lcp_timeout])
            # commit changes
            self.cli_commit()

            # Validate configuration values
            conf = ConfigParser(allow_no_value=True, delimiters='=')
            conf.read(self._config_file)

            self.assertEqual(conf['chap-secrets']['gw-ip-address'], self._gateway)

            # check ppp
            self.assertEqual(conf['ppp']['mppe'], mppe)
            self.assertEqual(conf['ppp']['min-mtu'], min_mtu)
            self.assertEqual(conf['ppp']['mru'], mru)

            self.assertEqual(conf['ppp']['ccp'], '0')

            # check interface-cache
            self.assertEqual(conf['ppp']['unit-cache'], interface_cache)

            # check ipv6
            for tmp in ['ipv6pool', 'ipv6_nd', 'ipv6_dhcp']:
                self.assertEqual(conf['modules'][tmp], None)

            self.assertEqual(conf['ppp']['ipv6'], allow_ipv6)
            self.assertEqual(conf['ppp']['ipv6-intf-id'], random)
            self.assertEqual(conf['ppp']['ipv6-peer-intf-id'], random)
            self.assertTrue(conf['ppp'].getboolean('ipv6-accept-peer-intf-id'))
            self.assertEqual(conf['ppp']['lcp-echo-failure'], lcp_failure)
            self.assertEqual(conf['ppp']['lcp-echo-interval'], lcp_interval)
            self.assertEqual(conf['ppp']['lcp-echo-timeout'], lcp_timeout)

        def test_accel_wins_server(self):
            self.basic_config()
            winsservers = ["192.0.2.1", "192.0.2.2"]
            for wins in winsservers:
                self.set(["wins-server", wins])
            self.cli_commit()
            conf = ConfigParser(allow_no_value=True, delimiters="=", strict=False)
            conf.read(self._config_file)
            for ws in winsservers:
                self.assertIn(ws, [conf["wins"]["wins1"], conf["wins"]["wins2"]])

        def test_accel_snmp(self):
            self.basic_config()
            self.set(['snmp', 'master-agent'])
            self.cli_commit()
            conf = ConfigParser(allow_no_value=True, delimiters="=", strict=False)
            conf.read(self._config_file)
            self.assertEqual(conf['modules']['net-snmp'], None)
            self.assertEqual(conf['snmp']['master'], '1')

        def test_accel_shaper(self):
            self.basic_config()
            fwmark = '2'
            self.set(['shaper', 'fwmark', fwmark])
            self.cli_commit()
            conf = ConfigParser(allow_no_value=True, delimiters="=", strict=False)
            conf.read(self._config_file)
            self.assertEqual(conf['modules']['shaper'], None)
            self.assertEqual(conf['shaper']['verbose'], '1')
            self.assertEqual(conf['shaper']['down-limiter'], 'tbf')
            self.assertEqual(conf['shaper']['fwmark'], fwmark)

        def test_accel_limits(self):
            self.basic_config()
            burst = '100'
            timeout = '20'
            limits = '1/min'
            self.set(['limits', 'connection-limit', limits])
            self.set(['limits', 'timeout', timeout])
            self.set(['limits', 'burst', burst])
            self.cli_commit()
            conf = ConfigParser(allow_no_value=True, delimiters="=", strict=False)
            conf.read(self._config_file)
            self.assertEqual(conf['modules']['connlimit'], None)
            self.assertEqual(conf['connlimit']['limit'], limits)
            self.assertEqual(conf['connlimit']['burst'], burst)
            self.assertEqual(conf['connlimit']['timeout'], timeout)

        def test_accel_log_level(self):
            self.basic_config()
            self.cli_commit()

            # check default value
            conf = ConfigParser(allow_no_value=True)
            conf.read(self._config_file)
            self.assertEqual(conf['log']['level'], '3')

            for log_level in range(0, 5):
                self.set(['log', 'level', str(log_level)])
                self.cli_commit()

                # Validate configuration values
                conf = ConfigParser(allow_no_value=True)
                conf.read(self._config_file)

                self.assertEqual(conf['log']['level'], str(log_level))

        def reconfigure_prepare(self):
            """
            Hook for configuration outside of the service which must exist
            before reconfiguration steps run, e.g. dummy interfaces
            """

        def run_reconfigure_steps(self, get_steps):
            """
            Apply each step returned by get_steps() as one commit on top of
            basic_config() and verify the daemon was reloaded and not restarted.
            Steps are built after basic_config() as they may depend on it.

            A step is a dict with the keys:
              name   - shown on failure
              set    - list of paths relative to the service base path
              delete - list of paths relative to the service base path
              check  - optional callable run after the commit
            Deletes are applied before sets.
            """
            self.basic_config()
            self.reconfigure_prepare()
            self.cli_commit()

            pid = self._accel_pid()
            self.assertIsNotNone(pid)

            steps = get_steps()
            if not steps:
                self.skipTest('No reconfiguration steps for this service')

            for step in steps:
                for path in step.get('delete', []):
                    self.delete(path)
                for path in step.get('set', []):
                    self.set(path)
                try:
                    self.cli_commit()
                except (AssertionError, ConfigSessionError) as e:
                    self.fail(f'Step "{step["name"]}": {e}')
                self.assertEqual(pid, self._accel_pid(),
                                 msg=f'Step "{step["name"]}" changed the daemon PID')
                if 'check' in step:
                    step['check']()

        def listening_sockets(self, proto):
            """ Local address:port of all listening TCP or UDP sockets """
            out = cmdl(['ss', '-Hln' + ('t' if proto == 'tcp' else 'u')])
            return [line.split()[3] for line in out.splitlines() if line.strip()]

        def assert_listening(self, proto, port, address=None, present=True):
            # The daemon re-reads its configuration asynchronously after the
            # reload signal, poll for the listener to show up or go away
            def match(sockets):
                for sock in sockets:
                    if address and sock == f'{address}:{port}':
                        return True
                    if not address and sock.rsplit(':', 1)[-1] == str(port):
                        return True
                return False

            found, sockets = self.wait_for_result(
                lambda: self.listening_sockets(proto),
                lambda sockets: match(sockets) == present, pause=0.5, timeout=5)
            where = f'{address}:{port}' if address else f'port {port}'
            self.assertTrue(found, msg=f'{proto} {where} expected '
                            f'{"listening" if present else "closed"}: {sockets}')

        def steps_local_users(self):
            user = ['authentication', 'local-users', 'username']
            return [
                {'name': 'add user', 'set': [user + ['user1', 'password', 'pass1']]},
                {'name': 'add second user', 'set': [user + ['user2', 'password', 'pass2']]},
                {'name': 'change password', 'set': [user + ['user1', 'password', 'pass1-new']]},
                {'name': 'add static-ip', 'set': [user + ['user1', 'static-ip', '192.0.2.101']]},
                {'name': 'change static-ip', 'set': [user + ['user1', 'static-ip', '192.0.2.102']]},
                {'name': 'delete static-ip', 'delete': [user + ['user1', 'static-ip']]},
                {'name': 'add rate-limit', 'set': [user + ['user1', 'rate-limit', 'upload', '1000'],
                                                   user + ['user1', 'rate-limit', 'download', '2000']]},
                {'name': 'change rate-limit', 'set': [user + ['user1', 'rate-limit', 'upload', '3000'],
                                                      user + ['user1', 'rate-limit', 'download', '4000']]},
                {'name': 'delete rate-limit', 'delete': [user + ['user1', 'rate-limit']]},
                {'name': 'disable user', 'set': [user + ['user2', 'disable']]},
                {'name': 'enable user', 'delete': [user + ['user2', 'disable']]},
                {'name': 'rename user', 'delete': [user + ['user2']],
                                        'set': [user + ['user3', 'password', 'pass3']]},
                {'name': 'delete users', 'delete': [user + ['user1'], user + ['user3']]},
            ]

        def steps_auth_protocols(self):
            if not self._ppp:
                return []
            proto = ['authentication', 'protocols']
            return [
                {'name': 'set pap', 'set': [proto + ['pap']]},
                {'name': 'add chap', 'set': [proto + ['chap']]},
                {'name': 'add mschap-v2', 'set': [proto + ['mschap-v2']]},
                {'name': 'replace protocols', 'delete': [proto],
                                              'set': [proto + ['mschap']]},
                {'name': 'delete protocols', 'delete': [proto]},
            ]

        def steps_radius(self):
            radius = ['authentication', 'radius']
            server1 = radius + ['server', '192.0.2.10']
            server2 = radius + ['server', '192.0.2.11']
            return [
                {'name': 'add server', 'set': [server1 + ['key', 'secret1']]},
                {'name': 'switch mode to radius', 'set': [['authentication', 'mode', 'radius']]},
                {'name': 'add second server', 'set': [server2 + ['key', 'secret2']]},
                {'name': 'change key', 'set': [server1 + ['key', 'secret1-new']]},
                {'name': 'change ports', 'set': [server1 + ['port', '2812'],
                                                 server1 + ['acct-port', '2813']]},
                {'name': 'disable accounting', 'delete': [server1 + ['acct-port']],
                                               'set': [server1 + ['disable-accounting']]},
                {'name': 'backup and priority', 'set': [server2 + ['backup'],
                                                        server2 + ['priority', '10']]},
                {'name': 'server fail-time', 'set': [server1 + ['fail-time', '10']]},
                {'name': 'timeouts', 'set': [radius + ['timeout', '5'],
                                             radius + ['acct-timeout', '10'],
                                             radius + ['max-try', '5']]},
                {'name': 'interim accounting', 'set': [radius + ['accounting-interim-interval', '60'],
                                                       radius + ['acct-interim-jitter', '10']]},
                {'name': 'preallocate-vif', 'set': [radius + ['preallocate-vif']]},
                {'name': 'add dynamic-author', 'set': [radius + ['dynamic-author', 'server', '192.0.2.20'],
                                                       radius + ['dynamic-author', 'key', 'coa-secret']]},
                {'name': 'change dynamic-author port', 'set': [radius + ['dynamic-author', 'port', '3799']]},
                {'name': 'nas settings', 'set': [radius + ['nas-identifier', 'VyOS-NAS'],
                                                 radius + ['nas-ip-address', '192.0.2.1']]},
                {'name': 'source-address', 'set': [radius + ['source-address', '192.0.2.1']]},
                {'name': 'message-authenticator', 'set': [
                    radius + ['message-authenticator', 'include-access-request'],
                    radius + ['message-authenticator', 'require-access-response']]},
                {'name': 'rate-limit', 'set': [radius + ['rate-limit', 'enable'],
                                               radius + ['rate-limit', 'attribute', 'Mikrotik-Rate-Limit'],
                                               radius + ['rate-limit', 'vendor', 'Mikrotik'],
                                               radius + ['rate-limit', 'multiplier', '1000']]},
                {'name': 'delete second server', 'delete': [server2]},
                {'name': 'delete dynamic-author', 'delete': [radius + ['dynamic-author']]},
                {'name': f'switch mode to {self._auth_mode}',
                         'set': [['authentication', 'mode', self._auth_mode]]},
                {'name': 'delete radius', 'delete': [radius]},
            ]

        def alternate_gateway(self):
            return '192.0.2.254'

        def steps_ipv4_pool(self):
            first_pool = 'SIMPLE-POOL'
            pool = 'client-ip-pool'
            return [
                {'name': 'add pool', 'set': [[pool, 'POOL2', 'range', '198.51.100.0/24']]},
                {'name': 'change pool range', 'delete': [[pool, 'POOL2', 'range']],
                                              'set': [[pool, 'POOL2', 'range', '198.51.100.0/25']]},
                {'name': 'add next-pool', 'set': [[pool, first_pool, 'next-pool', 'POOL2']]},
                {'name': 'switch default-pool', 'set': [['default-pool', 'POOL2']]},
                {'name': 'revert default-pool', 'set': [['default-pool', first_pool]]},
                {'name': 'add address-range pool', 'set': [[pool, 'POOL3', 'range', '203.0.113.10-203.0.113.20']]},
                {'name': 'delete address-range pool', 'delete': [[pool, 'POOL3']]},
                {'name': 'delete next-pool', 'delete': [[pool, first_pool, 'next-pool'], [pool, 'POOL2']]},
                {'name': 'change gateway-address', 'delete': [['gateway-address']],
                                                   'set': [['gateway-address', self.alternate_gateway()]]},
                {'name': 'revert gateway-address', 'delete': [['gateway-address']],
                                                   'set': [['gateway-address', self._gateway]]},
            ]

        def steps_ipv6(self):
            ppp = ['ppp-options']
            pool = ['client-ipv6-pool', 'V6-POOL']
            steps = []
            if self._ppp:
                steps.append({'name': 'enable ipv6', 'set': [ppp + ['ipv6', 'allow']]})
            steps += [
                {'name': 'add ipv6 pool', 'set': [pool + ['prefix', '2001:db8:1::/48', 'mask', '64']]},
                {'name': 'add prefix delegation', 'set': [pool + ['delegate', '2001:db8:2::/48',
                                                                  'delegation-prefix', '56']]},
                {'name': 'change mask', 'set': [pool + ['prefix', '2001:db8:1::/48', 'mask', '60']]},
                {'name': 'add second prefix', 'set': [pool + ['prefix', '2001:db8:3::/48', 'mask', '64']]},
                {'name': 'set default-ipv6-pool', 'set': [['default-ipv6-pool', 'V6-POOL']]},
                {'name': 'add ipv6 name-server', 'set': [['name-server', '2001:db8::53']]},
                {'name': 'delete ipv6 name-server', 'delete': [['name-server', '2001:db8::53']]},
            ]
            if self._ppp:
                steps += [
                    {'name': 'ipv6 prefer', 'set': [ppp + ['ipv6', 'prefer']]},
                    {'name': 'ipv6 require', 'set': [ppp + ['ipv6', 'require']]},
                    {'name': 'interface-id random', 'set': [ppp + ['ipv6-interface-id', 'random']]},
                    {'name': 'interface-id fixed', 'set': [ppp + ['ipv6-interface-id', '0:0:0:1']]},
                    {'name': 'peer interface-id random', 'set': [ppp + ['ipv6-peer-interface-id', 'random']]},
                    {'name': 'peer interface-id ipv4-addr', 'set': [ppp + ['ipv6-peer-interface-id', 'ipv4-addr']]},
                    {'name': 'peer interface-id calling-sid', 'set': [
                        ppp + ['ipv6-peer-interface-id', 'calling-sid'],
                        ppp + ['ipv6-peer-interface-id-secret', 'VyOS-IID-secret-0123']]},
                    {'name': 'change peer interface-id secret', 'set': [
                        ppp + ['ipv6-peer-interface-id-secret', 'VyOS-IID-secret-4567']]},
                    {'name': 'accept peer interface-id', 'set': [ppp + ['ipv6-accept-peer-interface-id']]},
                    {'name': 'delete interface-id settings', 'delete': [
                        ppp + ['ipv6-interface-id'], ppp + ['ipv6-peer-interface-id'],
                        ppp + ['ipv6-peer-interface-id-secret'], ppp + ['ipv6-accept-peer-interface-id']]},
                ]
            steps.append({'name': 'delete ipv6 pool', 'delete': [['default-ipv6-pool'], ['client-ipv6-pool']]})
            if self._ppp:
                steps.append({'name': 'disable ipv6', 'set': [ppp + ['ipv6', 'deny']]})
            return steps

        def steps_ppp_options(self):
            if not self._ppp:
                return []
            ppp = ['ppp-options']
            return [
                {'name': 'mppe require', 'set': [ppp + ['mppe', 'require']]},
                {'name': 'mppe deny', 'set': [ppp + ['mppe', 'deny']]},
                {'name': 'disable ccp', 'set': [ppp + ['disable-ccp']]},
                {'name': 'enable ccp', 'delete': [ppp + ['disable-ccp'], ppp + ['mppe']]},
                {'name': 'min-mtu and mru', 'set': [ppp + ['min-mtu', '1300'], ppp + ['mru', '1400']]},
                {'name': 'change mtu', 'set': [['mtu', '1400']]},
                {'name': 'ipv4 allow', 'set': [ppp + ['ipv4', 'allow']]},
                {'name': 'ipv4 require', 'set': [ppp + ['ipv4', 'require']]},
                {'name': 'lcp-echo', 'set': [ppp + ['lcp-echo-interval', '10'],
                                             ppp + ['lcp-echo-failure', '5'],
                                             ppp + ['lcp-echo-timeout', '60']]},
                {'name': 'interface-cache', 'set': [ppp + ['interface-cache', '1000']]},
                {'name': 'delete ppp-options', 'delete': [ppp, ['mtu']]},
            ]

        def steps_shaper(self):
            return [
                {'name': 'add shaper', 'set': [['shaper', 'fwmark', '2']]},
                {'name': 'change fwmark', 'set': [['shaper', 'fwmark', '3']]},
                {'name': 'delete shaper', 'delete': [['shaper']]},
            ]

        def steps_limits(self):
            return [
                {'name': 'add connection-limit', 'set': [['limits', 'connection-limit', '10/min'],
                                                         ['limits', 'burst', '5'],
                                                         ['limits', 'timeout', '30']]},
                {'name': 'change connection-limit', 'set': [['limits', 'connection-limit', '20/sec']]},
                {'name': 'delete limits', 'delete': [['limits']]},
                {'name': 'add max-concurrent-sessions', 'set': [['max-concurrent-sessions', '100']]},
                {'name': 'change max-concurrent-sessions', 'set': [['max-concurrent-sessions', '200']]},
                {'name': 'delete max-concurrent-sessions', 'delete': [['max-concurrent-sessions']]},
            ]

        def steps_misc(self):
            scripts = ['extended-scripts']
            steps = [
                {'name': 'add name-servers', 'set': [['name-server', '192.0.2.53'],
                                                     ['name-server', '192.0.2.54']]},
                {'name': 'delete name-server', 'delete': [['name-server', '192.0.2.54']]},
            ]
            if self._ppp:
                steps += [
                    {'name': 'add wins-server', 'set': [['wins-server', '192.0.2.137']]},
                    {'name': 'delete wins-server', 'delete': [['wins-server']]},
                ]
            steps += [
                {'name': 'enable snmp', 'set': [['snmp', 'master-agent']]},
                {'name': 'disable snmp', 'delete': [['snmp']]},
                {'name': 'thread-count half', 'set': [['thread-count', 'half']]},
                {'name': 'thread-count 1', 'set': [['thread-count', '1']]},
                {'name': 'delete thread-count', 'delete': [['thread-count']]},
                {'name': 'add description', 'set': [['description', 'VyOS-reload-test']]},
                {'name': 'change description', 'set': [['description', 'VyOS-reload-test-new']]},
                {'name': 'delete description', 'delete': [['description']]},
                {'name': 'add extended-scripts', 'set': [scripts + ['on-up', '/usr/bin/true'],
                                                         scripts + ['on-down', '/usr/bin/true'],
                                                         scripts + ['on-change', '/usr/bin/true'],
                                                         scripts + ['on-pre-up', '/usr/bin/true']]},
                {'name': 'change extended-scripts', 'set': [scripts + ['on-up', '/usr/bin/false']]},
                {'name': 'delete extended-scripts', 'delete': [scripts]},
                {'name': 'log level 5', 'set': [['log', 'level', '5']]},
                {'name': 'log level 0', 'set': [['log', 'level', '0']]},
                {'name': 'delete log', 'delete': [['log']]},
            ]
            return steps

        def steps_server_specific(self):
            """ Reconfiguration steps only valid for one server type """
            return []

        def test_accel_reconfigure_local_users(self):
            self.run_reconfigure_steps(self.steps_local_users)

        def test_accel_reconfigure_auth_protocols(self):
            self.run_reconfigure_steps(self.steps_auth_protocols)

        def test_accel_reconfigure_radius(self):
            self.run_reconfigure_steps(self.steps_radius)

        def test_accel_reconfigure_ipv4_pool(self):
            self.run_reconfigure_steps(self.steps_ipv4_pool)

        def test_accel_reconfigure_ipv6(self):
            self.run_reconfigure_steps(self.steps_ipv6)

        def test_accel_reconfigure_ppp_options(self):
            self.run_reconfigure_steps(self.steps_ppp_options)

        def test_accel_reconfigure_shaper(self):
            self.run_reconfigure_steps(self.steps_shaper)

        def test_accel_reconfigure_limits(self):
            self.run_reconfigure_steps(self.steps_limits)

        def test_accel_reconfigure_misc(self):
            self.run_reconfigure_steps(self.steps_misc)

        def test_accel_reconfigure_server_specific(self):
            self.run_reconfigure_steps(self.steps_server_specific)

        def test_accel_recreate_service_new_pid(self):
            # Deleting and re-creating the service is the only way to a new PID
            self.basic_config()
            self.cli_commit()
            pid = self._accel_pid()
            self.assertIsNotNone(pid)

            self.cli_delete(self._base_path)
            self.cli_commit()
            self.assertIsNone(self._accel_pid())

            self.basic_config()
            self.cli_commit()
            new_pid = self._accel_pid()
            self.assertIsNotNone(new_pid)
            self.assertNotEqual(pid, new_pid)
