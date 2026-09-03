# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

import importlib.machinery
import importlib.util
from unittest import TestCase

from vyos.configtree import ConfigTree

migration_script = 'src/migration-scripts/openvpn/5-to-6'

dco = ['interfaces', 'openvpn', 'vtun10', 'offload', 'dco']


def load_migrate():
    loader = importlib.machinery.SourceFileLoader('openvpn_5_to_6', migration_script)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module.migrate


def config_tree(body):
    return ConfigTree(
        'interfaces {\n'
        '    openvpn vtun10 {\n'
        f'{body}'
        '        offload {\n'
        '            dco\n'
        '        }\n'
        '    }\n'
        '}\n'
    )


class TestOpenVPNMigration(TestCase):
    def setUp(self):
        self.migrate = load_migrate()

    def test_empty_config(self):
        # must not raise when no OpenVPN interface is configured
        config = ConfigTree('system {\n    host-name vyos\n}\n')
        self.migrate(config)
        self.assertFalse(config.exists(['interfaces', 'openvpn']))

    def test_supported_dco_is_kept(self):
        config = config_tree(
            '        mode server\n'
            '        device-type tun\n'
            '        encryption {\n'
            '            data-ciphers aes256gcm\n'
            '        }\n'
            '        server {\n'
            '            topology subnet\n'
            '        }\n'
        )
        self.migrate(config)
        self.assertTrue(config.exists(dco))

    def test_compress_migrate_keeps_dco(self):
        # the option OpenVPN suggests for keeping the offload with legacy
        # clients must not cost the interface its offload
        config = config_tree(
            '        mode server\n        openvpn-option "--compress migrate"\n'
        )
        self.migrate(config)
        self.assertTrue(config.exists(dco))

    def test_compress_algorithm_drops_dco(self):
        config = config_tree(
            '        mode server\n        openvpn-option "--compress lzo"\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(dco))

    def test_allow_compression_no_keeps_dco(self):
        config = config_tree(
            '        mode server\n        openvpn-option "--allow-compression no"\n'
        )
        self.migrate(config)
        self.assertTrue(config.exists(dco))

    def test_allow_compression_asym_drops_dco(self):
        config = config_tree(
            '        mode server\n        openvpn-option "--allow-compression asym"\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(dco))

    def test_incompatible_option_drops_dco(self):
        config = config_tree(
            '        mode server\n        openvpn-option "--fragment 1300"\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(dco))

    def test_harmless_option_keeps_dco(self):
        config = config_tree(
            '        mode server\n        openvpn-option "--persist-tun"\n'
        )
        self.migrate(config)
        self.assertTrue(config.exists(dco))

    def test_interfaces_are_independent(self):
        # an interface without "offload" must be left alone, and dropping the
        # offload from one must not disturb another
        config = ConfigTree(
            'interfaces {\n'
            '    openvpn vtun10 {\n'
            '        mode server\n'
            '        device-type tap\n'
            '        offload {\n'
            '            dco\n'
            '        }\n'
            '    }\n'
            '    openvpn vtun11 {\n'
            '        mode server\n'
            '    }\n'
            '    openvpn vtun12 {\n'
            '        mode server\n'
            '        offload {\n'
            '            dco\n'
            '        }\n'
            '    }\n'
            '}\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(['interfaces', 'openvpn', 'vtun10', 'offload']))
        self.assertTrue(config.exists(['interfaces', 'openvpn', 'vtun11']))
        self.assertFalse(config.exists(['interfaces', 'openvpn', 'vtun11', 'offload']))
        self.assertTrue(
            config.exists(['interfaces', 'openvpn', 'vtun12', 'offload', 'dco'])
        )

    def test_minimal_dco_is_kept(self):
        # a plain tun server spells out neither device-type nor topology,
        # which is the usual shape of a saved configuration
        config = config_tree('        mode server\n')
        self.migrate(config)
        self.assertTrue(config.exists(dco))

    def test_tap_drops_dco(self):
        config = config_tree('        mode server\n        device-type tap\n')
        self.migrate(config)
        self.assertFalse(config.exists(dco))
        # the now empty parent must go too
        self.assertFalse(config.exists(dco[:-1]))

    def test_shared_secret_drops_dco(self):
        config = config_tree(
            '        mode site-to-site\n        shared-secret-key ovpn_test\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(dco))

    def test_lzo_drops_dco(self):
        config = config_tree('        mode server\n        use-lzo-compression\n')
        self.migrate(config)
        self.assertFalse(config.exists(dco))

    def test_cbc_cipher_drops_dco(self):
        config = config_tree(
            '        mode server\n'
            '        encryption {\n'
            '            data-ciphers aes256gcm\n'
            '            data-ciphers aes256\n'
            '        }\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(dco))

    def test_cbc_fallback_drops_dco(self):
        config = config_tree(
            '        mode site-to-site\n'
            '        encryption {\n'
            '            data-ciphers-fallback aes256\n'
            '        }\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(dco))

    def test_non_subnet_topology_drops_dco(self):
        config = config_tree(
            '        mode server\n'
            '        server {\n'
            '            topology net30\n'
            '        }\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(dco))

    def test_topology_ignored_outside_server_mode(self):
        # "server topology" is meaningless for a client, so it must not
        # cost that interface its offload
        config = config_tree(
            '        mode client\n'
            '        server {\n'
            '            topology net30\n'
            '        }\n'
        )
        self.migrate(config)
        self.assertTrue(config.exists(dco))

    def test_raw_cipher_list_drops_dco(self):
        config = config_tree(
            '        mode server\n'
            '        openvpn-option "--data-ciphers AES-256-CBC"\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(dco))

    def test_one_bad_cipher_in_a_raw_list_drops_dco(self):
        # OpenVPN gives up the offload over a single cipher it can not offload
        config = config_tree(
            '        mode server\n'
            '        openvpn-option "--data-ciphers AES-256-GCM:AES-256-CBC"\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(dco))

    def test_optional_raw_cipher_drops_dco(self):
        # a "?" only keeps OpenVPN from erroring out on an unknown cipher, a
        # known one still lands in the negotiation list
        config = config_tree(
            '        mode server\n'
            '        openvpn-option "--data-ciphers ?AES-256-CBC"\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(dco))

    def test_raw_cipher_fallback_drops_dco(self):
        config = config_tree(
            '        mode site-to-site\n'
            '        openvpn-option "--data-ciphers-fallback AES-256-CBC"\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(dco))

    def test_raw_ncp_ciphers_drops_dco(self):
        # OpenVPN still accepts the 2.4 name for "data-ciphers"
        config = config_tree(
            '        mode server\n'
            '        openvpn-option "--ncp-ciphers AES-256-CBC"\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(dco))

    def test_offloadable_raw_cipher_list_keeps_dco(self):
        # spelled as OpenVPN normalises it, and ChaCha20-Poly1305 is offloaded
        # too even though the CLI does not offer it
        config = config_tree(
            '        mode server\n'
            '        openvpn-option "--data-ciphers AES-256-GCM:CHACHA20-POLY1305"\n'
        )
        self.migrate(config)
        self.assertTrue(config.exists(dco))

    def test_raw_cipher_case_is_normalised(self):
        config = config_tree(
            '        mode server\n'
            '        openvpn-option "--data-ciphers aes-256-gcm"\n'
        )
        self.migrate(config)
        self.assertTrue(config.exists(dco))

    def test_valueless_raw_cipher_option_keeps_dco(self):
        # OpenVPN rejects it itself, the migration must not trip over it
        config = config_tree(
            '        mode server\n        openvpn-option "--data-ciphers"\n'
        )
        self.migrate(config)
        self.assertTrue(config.exists(dco))

    def test_default_raw_cipher_alias_keeps_dco(self):
        # "DEFAULT" is the built-in list, and OpenVPN expands it to AEAD
        # ciphers alone - it can never cost the interface its offload
        config = config_tree(
            '        mode server\n        openvpn-option "--data-ciphers DEFAULT"\n'
        )
        self.migrate(config)
        self.assertTrue(config.exists(dco))

    def test_default_raw_cipher_alias_is_case_sensitive(self):
        # OpenVPN matches the alias with strcmp(), so a lower case spelling is
        # just an unknown cipher
        config = config_tree(
            '        mode server\n        openvpn-option "--data-ciphers default"\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(dco))

    def test_default_raw_cipher_alias_with_a_bad_cipher_drops_dco(self):
        config = config_tree(
            '        mode server\n'
            '        openvpn-option "--data-ciphers DEFAULT:BF-CBC"\n'
        )
        self.migrate(config)
        self.assertFalse(config.exists(dco))
