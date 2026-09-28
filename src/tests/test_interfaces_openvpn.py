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

import importlib
import os
import unittest

from vyos import ConfigError

try:
    openvpn = importlib.import_module('src.conf_mode.interfaces_openvpn')
except ModuleNotFoundError:  # for unittest.main()
    import sys

    sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
    openvpn = importlib.import_module('src.conf_mode.interfaces_openvpn')


class TestRawMtuOption(unittest.TestCase):
    def test_sizing_options(self):
        # with or without the dashes, and wherever it is in the list
        for options, keyword in [
            (['--tun-mtu 1400'], 'tun-mtu'),
            (['tun-mtu 1400'], 'tun-mtu'),
            (['--verb 3', '--tun-mtu 1400'], 'tun-mtu'),
            (['--link-mtu 1450'], 'link-mtu'),
            (['link-mtu 1450'], 'link-mtu'),
            (['--udp-mtu 1450'], 'udp-mtu'),
        ]:
            with self.subTest(options=options):
                config = {'openvpn_option': options}
                self.assertEqual(openvpn.raw_mtu_option(config), keyword)

    def test_lookalikes(self):
        # options merely named alike, or carrying tun-mtu as an argument, do
        # not size the tunnel
        for options in [
            ['--tun-mtu-max 1600'],
            ['tun-mtu-extra 32'],
            ['push "tun-mtu 1400"'],
            ['--verb 3'],
            [''],
            [],
        ]:
            with self.subTest(options=options):
                config = {'openvpn_option': options}
                self.assertIsNone(openvpn.raw_mtu_option(config))

        self.assertIsNone(openvpn.raw_mtu_option({}))


class TestVerifyOpenvpnMtu(unittest.TestCase):
    def config(self, **kwargs):
        return {'ifname': 'vtun0', 'mode': 'server', **kwargs}

    def test_no_mtu(self):
        # nothing to check - not even a raw option on its own
        openvpn.verify_openvpn_mtu(self.config())
        openvpn.verify_openvpn_mtu(self.config(openvpn_option=['--tun-mtu 1400']))

    def test_raw_option_conflict(self):
        for option, keyword in [
            ('--tun-mtu 1400', 'tun-mtu'),
            ('--link-mtu 1450', 'link-mtu'),
            ('--udp-mtu 1450', 'udp-mtu'),
        ]:
            with self.subTest(option=option):
                config = self.config(mtu='1420', openvpn_option=[option])
                with self.assertRaisesRegex(
                    ConfigError, rf'openvpn-option\s+{keyword}'
                ):
                    openvpn.verify_openvpn_mtu(config)

        # a lookalike is no conflict
        config = self.config(mtu='1420', openvpn_option=['--tun-mtu-max 1600'])
        openvpn.verify_openvpn_mtu(config)

    def test_minimum_mtu(self):
        with self.assertRaisesRegex(ConfigError, r'at\s+least\s+100'):
            openvpn.verify_openvpn_mtu(self.config(mtu='99'))
        openvpn.verify_openvpn_mtu(self.config(mtu='100'))

    def test_ipv6_minimum_mtu(self):
        server = {'subnet': ['192.0.2.0/24', '2001:db8::/64']}
        local_address = {'2001:db8::1': {}}
        for kwargs in [
            {'server': server},
            {'mode': 'site-to-site', 'local_address': local_address},
        ]:
            with self.subTest(**kwargs):
                config = self.config(mtu='1279', **kwargs)
                with self.assertRaisesRegex(ConfigError, r'minimum\s+MTU'):
                    openvpn.verify_openvpn_mtu(config)
                openvpn.verify_openvpn_mtu(self.config(mtu='1280', **kwargs))

        # IPv4 alone may go below the IPv6 minimum
        for kwargs in [
            {'server': {'subnet': ['192.0.2.0/24']}},
            {'mode': 'site-to-site', 'local_address': {'10.0.0.1': {}}},
        ]:
            with self.subTest(**kwargs):
                openvpn.verify_openvpn_mtu(self.config(mtu='1200', **kwargs))


if __name__ == '__main__':
    unittest.main()
