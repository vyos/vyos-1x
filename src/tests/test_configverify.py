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
from vyos.config import ConfigDict
from vyos.configverify import verify_mirror_redirect


class TestVerifyMirrorRedirect(TestCase):
    # CLI "interfaces" tree, carried by the dictionaries returned from
    # Config.get_config_dict() in their interfaces_root attribute
    interfaces_root = {
        'dummy': {'dum4711': {}},
        'ethernet': {
            'eth0': {},
            'eth1': {'vif': {'100': {'address': ['192.0.2.1/24']}}},
        },
        'tunnel': {'tun4711': {'encapsulation': 'gre'}},
        # "tun4712" is a WireGuard peer name here, not an interface
        'wireguard': {'wg4711': {'peer': {'tun4712': {'address': '192.0.2.2'}}}},
    }

    def _config(self, ifname, **options):
        config = ConfigDict({'ifname': ifname, **options})
        config.interfaces_root = self.interfaces_root
        return config

    def test_target_in_kernel(self):
        verify_mirror_redirect(self._config('eth0', mirror={'ingress': 'lo'}))
        verify_mirror_redirect(self._config('eth0', redirect='lo'))

    def test_target_defined_on_cli_only(self):
        # T6393: target defined on the CLI but not (yet) created in the kernel
        verify_mirror_redirect(
            self._config('eth0', mirror={'ingress': 'tun4711', 'egress': 'dum4711'})
        )
        verify_mirror_redirect(self._config('eth0', redirect='tun4711'))
        verify_mirror_redirect(self._config('eth0.100', mirror={'ingress': 'tun4711'}))

    def test_target_missing(self):
        with self.assertRaisesRegex(ConfigError, 'mirror interface "tun4712"'):
            verify_mirror_redirect(self._config('eth0', mirror={'ingress': 'tun4712'}))
        with self.assertRaisesRegex(ConfigError, 'redirect interface "tun4712"'):
            verify_mirror_redirect(self._config('eth0', redirect='tun4712'))
        # VLAN target defined on the CLI but not existing in the kernel
        with self.assertRaises(ConfigError):
            verify_mirror_redirect(self._config('eth0', mirror={'egress': 'eth1.100'}))
        # without any knowledge of the CLI the kernel is the only reference
        with self.assertRaises(ConfigError):
            verify_mirror_redirect({'ifname': 'eth0', 'mirror': {'ingress': 'tun4711'}})

    def test_mirror_to_self(self):
        with self.assertRaises(ConfigError):
            verify_mirror_redirect(self._config('eth0', mirror={'ingress': 'eth0'}))

    def test_mirror_and_redirect_exclusive(self):
        with self.assertRaises(ConfigError):
            verify_mirror_redirect(
                self._config('eth0', mirror={'ingress': 'lo'}, redirect='lo')
            )
