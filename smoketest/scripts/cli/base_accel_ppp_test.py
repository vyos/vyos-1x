# Copyright (C) 2020-2024 VyOS maintainers and contributors
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
import unittest


from base_vyostest_shim import VyOSUnitTestSHIM
from configparser import ConfigParser

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.template import is_ipv4
from vyos.utils.system import get_half_cpus
from vyos.utils.process import process_named_running
from vyos.utils.process import cmd


class BasicAccelPPPTest:
    class TestCase(VyOSUnitTestSHIM.TestCase):
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

        def tearDown(self):
            # Check for running process
            self.assertTrue(process_named_running(self._process_name))

            self.cli_delete(self._base_path)
            self.cli_commit()

            # Check for running process
            self.assertFalse(process_named_running(self._process_name))

        def set(self, path):
            self.cli_set(self._base_path + path)

        def delete(self, path):
            self.cli_delete(self._base_path + path)

        def basic_protocol_specific_config(self):
            """
            An astract method.
            Initialize protocol scpecific configureations.
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
            where the first injection of end keyowrd
            :param start: start keyword
            :type start: str
            :param end: end keyword
            :type end: str
            :return: part of config
            :rtype: str
            """
            command = f'cat {self._config_file} | sed -n "/^\[{start}/,/^\[{end}/p"'
            out = cmd(command)
            return out

        def verify(self, conf):
            self.assertEqual(conf["core"]["thread-count"], str(get_half_cpus()))

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
            tmp = cmd(f"sudo cat {self._chap_secrets}")
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
            tmp = cmd(f"sudo cat {self._chap_secrets}")
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
            self.assertEqual(conf["radius"]["acct-interim-interval"], acct_interim_interval)
            self.assertEqual(conf["radius"]["acct-interim-jitter"], acct_interim_jitter)
            self.assertEqual(conf["radius"]["timeout"], "3")
            self.assertEqual(conf["radius"]["max-try"], "3")

            self.assertEqual(
                conf["radius"]["dae-server"], f"{coa_server}:1700,{coa_key}"
            )
            self.assertEqual(conf["radius"]["nas-identifier"], nas_id)
            self.assertEqual(conf["radius"]["nas-ip-address"], nas_ip)
            self.assertEqual(conf["radius"]["bind"], source_address)

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
                ['client-ipv6-pool', pool_name, 'prefix', prefix_1, 'mask',
                 prefix_mask])
            self.set(
                ['client-ipv6-pool', pool_name, 'prefix', prefix_2, 'mask',
                 prefix_mask])

            delegate_1_prefix = '2001:db8:fff1::/56'
            delegate_2_prefix = '2001:db8:fff2::/56'
            delegate_mask = '64'
            self.set(
                ['client-ipv6-pool', pool_name, 'delegate', delegate_1_prefix,
                 'delegation-prefix', delegate_mask])
            self.set(
                ['client-ipv6-pool', pool_name, 'delegate', delegate_2_prefix,
                 'delegation-prefix', delegate_mask])

            # commit changes
            self.cli_commit()

            # Validate configuration values
            conf = ConfigParser(allow_no_value=True, delimiters='=',
                                strict=False)
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
