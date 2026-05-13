#!/usr/bin/env python3

import unittest
from pathlib import Path

from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.configsession import ConfigSessionError


base_path = ['interfaces', 'zerotier']
service_path = ['service', 'zerotier']
config_dir = Path('/run/vyos-zerotier')
identity_secret = 'c172e8159d:0:0eb12171f8c710e338db67f0a9b8989c85c08908fc70fcf2fbd7d486d82a825414db85244c450d38e139c1e5a8415cb47dc7edd026fd4a3fe07da3ce8ecffef7:e564a44f6eb0d32e32b04d2f0a33b34a7a0b47dec76ef5b241977756646955be83d802e07884699cd11d7d41a7ee9654891af703d7d444e74cfdeb50d17b1f28'


class TestZeroTier(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestZeroTier, cls).setUpClass()
        cls.cli_delete(cls, base_path)
        cls.cli_delete(cls, service_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_delete(service_path)
        self.cli_commit()

    def configure_identity(self):
        self.cli_set(service_path + ['identity', 'secret', identity_secret])

    def test_basic_interface_files(self):
        self.configure_identity()
        self.cli_set(base_path + ['zt0', 'network-id', '0123456789abcdef'])
        self.cli_commit()

        self.assertTrue((config_dir / 'identity.secret').exists())
        self.assertTrue((config_dir / 'identity.public').exists())
        self.assertEqual((config_dir / 'devicemap').read_text(), '0123456789abcdef=zt0\n')
        self.assertTrue((config_dir / 'networks.d' / '0123456789abcdef.conf').exists())

        local = (config_dir / 'networks.d' / '0123456789abcdef.local.conf').read_text()
        self.assertIn('allowManaged=1\n', local)

    def test_manual_address_disables_managed_addressing(self):
        self.configure_identity()
        self.cli_set(base_path + ['zt0', 'network-id', '0123456789abcdef'])
        self.cli_set(base_path + ['zt0', 'address', '192.0.2.1/24'])
        self.cli_commit()

        local = (config_dir / 'networks.d' / '0123456789abcdef.local.conf').read_text()
        self.assertIn('allowManaged=0\n', local)

    def test_manual_address_rejects_allow_managed(self):
        self.configure_identity()
        self.cli_set(base_path + ['zt0', 'network-id', '0123456789abcdef'])
        self.cli_set(base_path + ['zt0', 'address', '192.0.2.1/24'])
        self.cli_set(base_path + ['zt0', 'allow-managed'])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

    def test_duplicate_network_id_rejected(self):
        self.configure_identity()
        self.cli_set(base_path + ['zt0', 'network-id', '0123456789abcdef'])
        self.cli_set(base_path + ['zt1', 'network-id', '0123456789abcdef'])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()


if __name__ == '__main__':
    unittest.main(verbosity=2)
