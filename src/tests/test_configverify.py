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

from unittest import TestCase
from vyos import ConfigError
from vyos.configverify import is_interface_defined
from vyos.configverify import verify_diffie_hellman_length
from vyos.configverify import verify_mirror_redirect
from vyos.utils.process import cmdl

dh_file = '/tmp/dh.pem'

class TestDictSearch(TestCase):
    def setUp(self):
        pass

    def test_dh_key_none(self):
        self.assertFalse(verify_diffie_hellman_length('/tmp/non_existing_file', '1024'))

    def test_dh_key_512(self):
        key_len = '512'
        cmdl(['openssl', 'dhparam', '-out', dh_file, key_len])
        self.assertTrue(verify_diffie_hellman_length(dh_file, key_len))


# Dictionaries returned by Config.get_config_dict() carry the CLI "interfaces"
# tree in their interfaces_root attribute
class _ConfigDict(dict):
    pass


class TestVerifyMirrorRedirect(TestCase):

    interfaces_root = {
        'dummy': {'dum4711': {}},
        'ethernet': {
            'eth0': {},
            'eth1': {'vif': {'100': {'address': ['192.0.2.1/24']}}},
        },
        'tunnel': {'tun4711': {'encapsulation': 'gre'}},
    }

    def _config(self, ifname, mirror):
        config = _ConfigDict({'ifname': ifname, 'mirror': mirror})
        config.interfaces_root = self.interfaces_root
        return config

    def test_is_interface_defined(self):
        root = self.interfaces_root
        self.assertTrue(is_interface_defined(root, 'eth0'))
        self.assertTrue(is_interface_defined(root, 'dum4711'))
        self.assertTrue(is_interface_defined(root, 'tun4711'))
        self.assertFalse(is_interface_defined(root, 'eth2'))
        self.assertFalse(is_interface_defined(root, 'tun0'))
        self.assertFalse(is_interface_defined(root, 'nonsense0'))
        self.assertFalse(is_interface_defined(root, 'eth1.100'))
        self.assertFalse(is_interface_defined({}, 'eth0'))
        self.assertFalse(is_interface_defined(None, 'eth0'))

    def test_mirror_target_in_kernel(self):
        verify_mirror_redirect(self._config('eth0', {'ingress': 'lo'}))

    def test_mirror_target_defined_on_cli_only(self):
        # T6393: target defined on the CLI but not (yet) created in the kernel
        verify_mirror_redirect(
            self._config('eth0', {'ingress': 'tun4711', 'egress': 'dum4711'})
        )
        # VLAN sub-interface (source) dictionaries have no interfaces_root
        # attribute, the caller need to pass it explicitly
        verify_mirror_redirect(
            {'ifname': 'eth0.100', 'mirror': {'ingress': 'tun4711'}},
            interfaces_root=self.interfaces_root,
        )

    def test_mirror_target_missing(self):
        with self.assertRaises(ConfigError):
            verify_mirror_redirect(self._config('eth0', {'ingress': 'tun4712'}))
        # VLAN target defined on the CLI but not existing in the kernel
        with self.assertRaises(ConfigError):
            verify_mirror_redirect(self._config('eth0', {'egress': 'eth1.100'}))
        # without any knowledge of the CLI the kernel is the only reference
        with self.assertRaises(ConfigError):
            verify_mirror_redirect(
                {'ifname': 'eth0.100', 'mirror': {'ingress': 'tun4711'}}
            )

    def test_mirror_to_self(self):
        with self.assertRaises(ConfigError):
            verify_mirror_redirect(self._config('eth0', {'ingress': 'eth0'}))

    def test_mirror_and_redirect_exclusive(self):
        config = self._config('eth0', {'ingress': 'lo'})
        config['redirect'] = 'lo'
        with self.assertRaises(ConfigError):
            verify_mirror_redirect(config)
