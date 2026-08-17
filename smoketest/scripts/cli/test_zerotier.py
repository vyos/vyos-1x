#!/usr/bin/env python3

import unittest
from pathlib import Path

from base_vyostest_shim import VyOSUnitTestSHIM
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

    def test_basic_interface_runtime_files(self):
        self.configure_identity()
        self.cli_set(base_path + ['zt0', 'network-id', '0123456789abcdef'])
        self.cli_commit()

        self.assertTrue((config_dir / 'identity.secret').exists())
        self.assertTrue((config_dir / 'identity.public').exists())
        self.assertTrue((config_dir / 'local.conf').exists())
        self.assertFalse((config_dir / 'devicemap').exists())
        self.assertFalse((config_dir / 'interfaces.json').exists())
        self.assertFalse((config_dir / 'networks.d' / '0123456789abcdef.conf').exists())
        self.assertFalse((config_dir / 'networks.d' / '0123456789abcdef.local.conf').exists())

    def test_allow_managed_defaults_to_true(self):
        self.configure_identity()
        self.cli_set(base_path + ['zt0', 'network-id', '0123456789abcdef'])
        self.cli_commit()

        self.assertFalse((config_dir / 'networks.d' / '0123456789abcdef.local.conf').exists())

    def test_allow_managed_accepts_false(self):
        self.configure_identity()
        self.cli_set(base_path + ['zt0', 'network-id', '0123456789abcdef'])
        self.cli_set(base_path + ['zt0', 'allow-managed', 'false'])
        self.cli_commit()

        self.assertFalse((config_dir / 'networks.d' / '0123456789abcdef.local.conf').exists())

    def test_manual_address_keeps_explicit_managed_policy(self):
        self.configure_identity()
        self.cli_set(base_path + ['zt0', 'network-id', '0123456789abcdef'])
        self.cli_set(base_path + ['zt0', 'address', '192.0.2.1/24'])
        self.cli_set(base_path + ['zt0', 'allow-managed', 'true'])
        self.cli_commit()

        self.assertFalse((config_dir / 'networks.d' / '0123456789abcdef.local.conf').exists())

    def test_duplicate_network_id_rejected(self):
        self.configure_identity()
        self.cli_set(base_path + ['zt0', 'network-id', '0123456789abcdef'])
        self.cli_set(base_path + ['zt1', 'network-id', '0123456789abcdef'])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()


if __name__ == '__main__':
    unittest.main(verbosity=2)
