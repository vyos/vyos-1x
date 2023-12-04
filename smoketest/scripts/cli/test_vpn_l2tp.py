#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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

from base_accel_ppp_test import BasicAccelPPPTest
from configparser import ConfigParser
from vyos.utils.process import cmd


class TestVPNL2TPServer(BasicAccelPPPTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['vpn', 'l2tp', 'remote-access']
        cls._config_file = '/run/accel-pppd/l2tp.conf'
        cls._chap_secrets = '/run/accel-pppd/l2tp.chap-secrets'
        cls._protocol_section = 'l2tp'
        # call base-classes classmethod
        super(TestVPNL2TPServer, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(TestVPNL2TPServer, cls).tearDownClass()

    def basic_protocol_specific_config(self):
        pass

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
        self.delete(["authentication", "local-users", "username", user, "static-ip"])
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
        self.assertEqual(conf["radius"]["acct-timeout"], "3")
        self.assertEqual(conf["radius"]["timeout"], "3")
        self.assertEqual(conf["radius"]["max-try"], "3")

        self.assertEqual(conf["radius"]["nas-identifier"], nas_id)
        self.assertEqual(conf["radius"]["nas-ip-address"], nas_ip)
        self.assertEqual(conf["radius"]["bind"], source_address)

        server = conf["radius"]["server"].split(",")
        self.assertEqual(radius_server, server[0])
        self.assertEqual(radius_key, server[1])
        self.assertEqual(f"auth-port={radius_port}", server[2])
        self.assertEqual(f"req-limit=0", server[4])
        self.assertEqual(f"fail-time=0", server[5])

        #
        # Disable Radius Accounting
        #
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
