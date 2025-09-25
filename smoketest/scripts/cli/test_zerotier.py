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

import json

import unittest
from pathlib import Path
from typing import Any


from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.utils.process import cmd
from vyos.utils.dict import dict_search
from vyos.utils.dict import dict_search_args

# Base config path for this feature
base_path = ['interfaces', 'zerotier']
config_directory = Path('/config/vyos-generated-zerotier')
unit_path = Path('/run/systemd/system')

class TestInterfacesZerotier(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestInterfacesZerotier, cls).setUpClass()
        cls.cli_delete(cls, base_path)
        if not config_directory.exists():
            config_directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, base_path)
        super(TestInterfacesZerotier, cls).tearDownClass()

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_delete(['firewall'])
        self.cli_commit()

    def load_json(self, interface: str = 'zt1') -> dict[str, Any]:
        """
        Load and validate a ZeroTier local.conf file for a given interface.

        Args:
            interface (str, optional): ZeroTier interface name used to resolve
                                    the config directory (default: 'zt1').

        Returns:
            dict[str, Any]: Parsed JSON contents of local.conf.

        Raises:
            AssertionError: If the file contents are not valid JSON (via assertTrue).
        """
        tmp_config_directory = config_directory / interface
        tmp_local_conf_file = tmp_config_directory / 'local.conf'
        local_conf = tmp_local_conf_file.read_text()

        try:
            local_conf_output = json.loads(local_conf)
            valid_json = True
        except Exception:
            valid_json = False

        self.assertTrue(valid_json)

        return local_conf_output

    def validate_zt(self, local_conf: dict, key: str, expected, info_path='settings', interface='zt1'):
        """
        Validate a ZeroTier setting in both a parsed local.conf dictionary and
        the runtime status reported by zerotier-cli.

        Args:
            local_conf (dict): Parsed JSON contents of local.conf.
            key (str): One or more nested keys (unpacked by dict_search_args)
                    representing the setting to validate.
            expected: Expected value for the setting (bool, int, str, etc.).
            info_path (str, optional): Base path in local.conf under which
                                    the key resides (default: 'settings').
            interface (str, optional): ZeroTier interface name used to resolve
                                    the config directory (default: 'zt1').
        """
        tmp_config_directory = config_directory / interface

        self.assertEqual(dict_search_args(local_conf, info_path, *key), expected)

        # Load and check zerotier-cli status
        status = json.loads(cmd(f"zerotier-cli -j -D{tmp_config_directory} info"))
        self.assertEqual(dict_search_args(status, 'config', info_path, *key), expected)


    def test_basic(self):
        authtoken = config_directory / 'zt1' / 'authtoken.secret'
        unit_file_path = unit_path  / 'vyos-zerotier-zt1.service'
        network_file = config_directory / 'zt1' / 'networks.d' / '0123456789abcdef.conf'
        tmp_config_directory = config_directory / 'zt1'

        self.cli_set(base_path + ['zt1', 'primary','port', '9993'])
        self.cli_set(base_path + ['zt1', 'network-id', '0123456789abcdef'])
        self.cli_commit()

        # Load and check local.conf; ensure valid JSON
        local_conf = self.load_json()

        self.assertTrue(unit_file_path.exists())
        self.assertTrue(authtoken.exists())
        self.assertTrue(network_file.exists())

        status = json.loads(cmd(f'zerotier-cli -j -D{tmp_config_directory} info'))
        self.assertNotEqual(dict_search('online', status), None)

        self.assertEqual(dict_search('config.settings.primaryPort', status), 9993)

    def test_bind(self):
        tmp_config_directory = config_directory / 'zt1'

        self.cli_set(['interfaces', 'dummy', 'dum0', 'address', '192.168.1.1/24'])
        self.cli_set(['interfaces', 'dummy', 'dum1', 'address', '192.168.2.1/24'])
        self.cli_set(base_path + ['zt1', 'network-id', '0123456789abcdef'])
        self.cli_set(base_path + ['zt1', 'primary', 'port', '9993'])
        self.cli_set(base_path + ['zt1', 'listen-address', '192.168.1.1'])
        self.cli_commit()

        # Load and check local.conf; ensure valid JSON
        local_conf = self.load_json()

        self.validate_zt(local_conf, ['bind'], ['192.168.1.1'])

    def test_custom_bonding_policy(self):
        self.cli_set(base_path + ['zt1', 'network-id', '0123456789abcdef'])
        self.cli_set(base_path + ['zt1', 'primary', 'port', '9993'])
        self.cli_set(base_path + ['zt3', 'network-id', '0123456789abcdef'])
        self.cli_set(base_path + ['zt3', 'primary', 'port', '9995'])

        self.cli_set(base_path + ['zt1', 'custom-policy', 'AB', 'base-policy', 'active-backup'])
        self.cli_set(base_path + ['zt1', 'custom-policy', 'AB', 'link-select-method', 'always'])
        self.cli_set(base_path + ['zt1', 'custom-policy', 'AB', 'failover-interval', '1000'])
        self.cli_set(base_path + ['zt1', 'custom-policy', 'AB', 'up-delay', '1000'])
        self.cli_set(base_path + ['zt1', 'custom-policy', 'AB', 'down-delay', '1000'])
        self.cli_set(base_path + ['zt1', 'custom-policy', 'AB', 'links', 'eth0', 'mode', 'primary'])
        self.cli_set(base_path + ['zt1', 'custom-policy', 'AB', 'links', 'eth1', 'mode', 'spare'])
        self.cli_set(base_path + ['zt1', 'custom-policy', 'AB', 'links', 'eth2', 'mode', 'spare'])

        self.cli_set(base_path + ['zt1', 'custom-policy', 'BA', 'base-policy', 'balance-aware'])
        self.cli_set(base_path + ['zt1', 'custom-policy', 'BA', 'failover-interval', '1000'])
        self.cli_set(base_path + ['zt1', 'custom-policy', 'BA', 'link-quality', 'latency-weight', '0.5'])
        self.cli_set(base_path + ['zt1', 'custom-policy', 'BA', 'link-quality', 'variance-weight', '0.5'])
        self.cli_set(base_path + ['zt1', 'custom-policy', 'BA', 'link-quality', 'max-latency', '500'])
        self.cli_set(base_path + ['zt1', 'custom-policy', 'BA', 'link-quality', 'max-variance', '20'])
        self.cli_set(base_path + ['zt1', 'custom-policy', 'BA', 'links', 'eth0', 'capacity', '1000000'])
        self.cli_set(base_path + ['zt1', 'custom-policy', 'BA', 'links', 'eth1', 'capacity', '250000'])

        self.cli_set(base_path + ['zt1', 'custom-policy', 'RR', 'base-policy', 'balance-rr'])

        self.cli_commit()

        # Load and check local.conf; ensure valid JSON
        local_conf = self.load_json()

        self.validate_zt(local_conf, ['policies', 'AB', 'basePolicy'], 'active-backup')
        self.validate_zt(local_conf, ['policies', 'AB', 'linkSelectMethod'], 'always')
        self.validate_zt(local_conf, ['policies', 'AB', 'failoverInterval'], 1000)
        self.validate_zt(local_conf, ['policies', 'AB', 'upDelay'], 1000)
        self.validate_zt(local_conf, ['policies', 'AB', 'downDelay'], 1000)
        self.validate_zt(local_conf, ['policies', 'AB', 'links', 'eth0', 'mode'], 'primary')
        self.validate_zt(local_conf, ['policies', 'AB', 'links', 'eth1', 'mode'], 'spare')
        self.validate_zt(local_conf, ['policies', 'AB', 'links', 'eth2', 'mode'], 'spare')

        self.validate_zt(local_conf, ['policies', 'BA', 'basePolicy'], 'balance-aware')
        self.validate_zt(local_conf, ['policies', 'BA', 'failoverInterval'], 1000)
        self.validate_zt(local_conf, ['policies', 'BA', 'linkQuality', 'lat_weight'], 0.5)
        self.validate_zt(local_conf, ['policies', 'BA', 'linkQuality', 'pdv_weight'], 0.5)
        self.validate_zt(local_conf, ['policies', 'BA', 'linkQuality', 'lat_max'], 500)
        self.validate_zt(local_conf, ['policies', 'BA', 'linkQuality', 'pdv_max'], 20)
        self.validate_zt(local_conf, ['policies', 'BA', 'links', 'eth0', 'capacity'], 1000000)
        self.validate_zt(local_conf, ['policies', 'BA', 'links', 'eth1', 'capacity'], 250000)

        self.validate_zt(local_conf, ['policies', 'RR', 'basePolicy'], 'balance-rr')

    def test_custom_ports(self):
        self.cli_set(base_path + ['zt1', 'network-id', '0123456789abcdef'])
        self.cli_set(base_path + ['zt1', 'primary', 'port', '9995'])
        self.cli_set(base_path + ['zt1', 'secondary', 'port', '9996'])
        self.cli_set(base_path + ['zt1', 'tertiary', 'port', '9997'])
        self.cli_commit()

        # Load and check local.conf; ensure valid JSON
        local_conf = self.load_json()

        self.validate_zt(local_conf, ['primaryPort'], 9995)
        self.validate_zt(local_conf, ['secondaryPort'], 9996)
        self.validate_zt(local_conf, ['tertiaryPort'], 9997)

    def test_generic_local_conf(self):
        self.cli_set(base_path + ['zt1', 'primary', 'port', '9993'])
        self.cli_set(base_path + ['zt1', 'network-id', '0123456789abcdef'])

        self.cli_set(base_path + ['zt1', 'allow-mgmt-from', '192.168.1.0/24'])
        self.cli_set(base_path + ['zt1', 'bonding-policy', 'active-backup'])
        self.cli_set(base_path + ['zt1', 'disable-port-mapping'])
        self.cli_set(base_path + ['zt1', 'disable-secondary-port'])
        self.cli_set(base_path + ['zt1', 'disable-tcp-fallback'])
        self.cli_set(base_path + ['zt1', 'force-tcp-relay'])
        self.cli_set(base_path + ['zt1', 'low-bandwidth-mode'])
        self.cli_set(base_path + ['zt1', 'multicore-options', 'enabled'])
        self.cli_set(base_path + ['zt1', 'multicore-options', 'core-count','2'])
        self.cli_set(base_path + ['zt1', 'multicore-options', 'cpu-pinning'])
        self.cli_set(base_path + ['zt1', 'multipath-mode', '2'])
        self.cli_set(base_path + ['zt1', 'tcp-relay', '192.168.0.1/443'])

        self.cli_set(base_path + ['zt1', 'network-config', '10.0.0.0/24', 'blacklist'])
        self.cli_set(base_path + ['zt1', 'network-config', '10.0.0.0/24', 'mtu', '1328'])

        self.cli_set(base_path + ['zt1', 'peer-config', '0123456789', 'blacklist', '10.0.1.0/24'])
        self.cli_set(base_path + ['zt1', 'peer-config', '0123456789', 'try', '10.0.3.1/9993'])
        self.cli_set(base_path + ['zt1', 'peer-config', '0123456789', 'try', '10.0.3.2/9993'])

        self.cli_commit()

        # Load and check local.conf; ensure valid JSON
        local_conf = self.load_json()

        self.validate_zt(local_conf, ['allowSecondaryPort'], False)
        self.validate_zt(local_conf, ['allowTcpFallbackRelay'], False)
        self.validate_zt(local_conf, ['concurrency'], 2)
        self.validate_zt(local_conf, ['cpuPinningEnabled'], True)
        self.validate_zt(local_conf, ['forceTcpRelay'], True)
        self.validate_zt(local_conf, ['lowBandwidthMode'], True)
        self.validate_zt(local_conf, ['multicoreEnabled'], True)
        self.validate_zt(local_conf, ['multipathMode'], 2)
        self.validate_zt(local_conf, ['portMappingEnabled'], False)
        self.validate_zt(local_conf, ['tcpFallbackRelay'], '192.168.0.1/443')
        self.validate_zt(local_conf, ['allowManagementFrom'], ['192.168.1.0/24'])
        self.validate_zt(local_conf, ['defaultBondingPolicy'], 'active-backup')
        self.validate_zt(local_conf, ['10.0.0.0/24', 'blacklist'], True, info_path='physical')
        self.validate_zt(local_conf, ['10.0.0.0/24', 'mtu'], 1328, info_path='physical')
        self.validate_zt(local_conf, ['0123456789', 'blacklist'], ['10.0.1.0/24'], info_path='virtual')
        self.validate_zt(local_conf, ['0123456789', 'try'], ['10.0.3.1/9993', '10.0.3.2/9993'], info_path='virtual')

    def test_interface_blacklist(self):
        self.cli_set(['interfaces', 'ethernet', 'eth0', 'address', '192.168.1.1/24'])
        self.cli_set(['interfaces', 'dummy', 'dum1', 'address', '192.168.2.1/24'])
        self.cli_set(['protocols', 'static', 'route', '0.0.0.0/0', 'next-hop', '192.168.1.1'])
        self.cli_set(base_path + ['zt1', 'network-id', '0123456789abcdef'])
        self.cli_set(base_path + ['zt1', 'primary', 'port', '9993'])
        self.cli_set(base_path + ['zt1', 'interface-blacklist', 'dum'])
        self.cli_commit()

        # Load and check local.conf; ensure valid JSON
        local_conf = self.load_json()

        self.validate_zt(local_conf, ['interfacePrefixBlacklist'], ['dum'])

    def test_multiple_interfaces(self):
        self.cli_set(base_path + ['zt1', 'primary', 'port', '9993'])
        self.cli_set(base_path + ['zt1', 'network-id', '0123456789abcdef'])
        self.cli_set(base_path + ['zt2', 'primary', 'port', '9994'])
        self.cli_set(base_path + ['zt2', 'network-id', '123456789abcdef0'])
        self.cli_commit()

        # Load and check local.conf; ensure valid JSON
        local_conf = self.load_json('zt1')
        self.validate_zt(local_conf, ['primaryPort'], 9993, interface='zt1')

        local_conf = self.load_json('zt2')
        self.validate_zt(local_conf, ['primaryPort'], 9994, interface='zt2')

    def test_peer_specific_bonds(self):
        self.cli_set(base_path + ['zt1', 'network-id', '0123456789abcdef'])
        self.cli_set(base_path + ['zt1', 'primary', 'port', '9993'])
        self.cli_set(base_path + ['zt1', 'custom-policy', 'custom_policy1', 'base-policy', 'active-backup'])
        self.cli_set(base_path + ['zt1', 'custom-policy', 'custom_policy1', 'link-select-method', 'always'])
        self.cli_set(base_path + ['zt1', 'peer-specific-bonds', '0123456789', 'bonding-policy', 'balance-rr'])
        self.cli_set(base_path + ['zt1', 'peer-specific-bonds', '1234567890', 'bonding-policy', 'custom_policy1'])
        self.cli_commit()

        # Load and check local.conf; ensure valid JSON
        local_conf = self.load_json()

        self.validate_zt(local_conf, ['peerSpecificBonds', '0123456789'], 'balance-rr')
        self.validate_zt(local_conf, ['peerSpecificBonds', '1234567890'], 'custom_policy1')

if __name__ == '__main__':
    unittest.main(verbosity=2)
