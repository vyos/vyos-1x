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

import vyos.template

from vyos.utils.network import interface_exists
from ipaddress import ip_network
from unittest import TestCase

class TestVyOSTemplate(TestCase):
    def setUp(self):
        pass

    def test_is_interface(self):
        for interface in ['lo', 'eth0']:
            if interface_exists(interface):
                self.assertTrue(vyos.template.is_interface(interface))
            else:
                self.assertFalse(vyos.template.is_interface(interface))
        self.assertFalse(vyos.template.is_interface('non-existent'))

    def test_is_ip(self):
        self.assertTrue(vyos.template.is_ip('192.0.2.1'))
        self.assertTrue(vyos.template.is_ip('2001:db8::1'))
        self.assertFalse(vyos.template.is_ip('VyOS'))

    def test_is_ipv4(self):
        self.assertTrue(vyos.template.is_ipv4('192.0.2.1'))
        self.assertTrue(vyos.template.is_ipv4('192.0.2.0/24'))
        self.assertTrue(vyos.template.is_ipv4('192.0.2.1/32'))

        self.assertFalse(vyos.template.is_ipv4('2001:db8::1'))
        self.assertFalse(vyos.template.is_ipv4('2001:db8::/64'))
        self.assertFalse(vyos.template.is_ipv4('VyOS'))

    def test_is_ipv6(self):
        self.assertTrue(vyos.template.is_ipv6('2001:db8::1'))
        self.assertTrue(vyos.template.is_ipv6('2001:db8::/64'))
        self.assertTrue(vyos.template.is_ipv6('2001:db8::1/64'))

        self.assertFalse(vyos.template.is_ipv6('192.0.2.1'))
        self.assertFalse(vyos.template.is_ipv6('192.0.2.0/24'))
        self.assertFalse(vyos.template.is_ipv6('192.0.2.1/32'))
        self.assertFalse(vyos.template.is_ipv6('VyOS'))

    def test_address_from_cidr(self):
        self.assertEqual(vyos.template.address_from_cidr('192.0.2.0/24'),  '192.0.2.0')
        self.assertEqual(vyos.template.address_from_cidr('2001:db8::/48'), '2001:db8::')

        with self.assertRaises(ValueError):
            # ValueError: 192.0.2.1/24 has host bits set
            self.assertEqual(vyos.template.address_from_cidr('192.0.2.1/24'),  '192.0.2.1')

        with self.assertRaises(ValueError):
            # ValueError: 2001:db8::1/48 has host bits set
            self.assertEqual(vyos.template.address_from_cidr('2001:db8::1/48'), '2001:db8::1')

        network_v4 = '192.0.2.0/26'
        self.assertEqual(vyos.template.address_from_cidr(network_v4), str(ip_network(network_v4).network_address))

    def test_netmask_from_cidr(self):
        self.assertEqual(vyos.template.netmask_from_cidr('192.0.2.0/24'),  '255.255.255.0')
        self.assertEqual(vyos.template.netmask_from_cidr('192.0.2.128/25'),  '255.255.255.128')
        self.assertEqual(vyos.template.netmask_from_cidr('2001:db8::/48'), 'ffff:ffff:ffff::')

        with self.assertRaises(ValueError):
            # ValueError: 192.0.2.1/24 has host bits set
            self.assertEqual(vyos.template.netmask_from_cidr('192.0.2.1/24'),  '255.255.255.0')

        with self.assertRaises(ValueError):
            # ValueError: 2001:db8:1:/64 has host bits set
            self.assertEqual(vyos.template.netmask_from_cidr('2001:db8:1:/64'), 'ffff:ffff:ffff:ffff::')

        network_v4 = '192.0.2.0/26'
        self.assertEqual(vyos.template.netmask_from_cidr(network_v4), str(ip_network(network_v4).netmask))

    def test_first_host_address(self):
        self.assertEqual(vyos.template.first_host_address('10.0.0.0/24'), '10.0.0.1')
        self.assertEqual(vyos.template.first_host_address('10.0.0.10/24'), '10.0.0.1')
        self.assertEqual(vyos.template.first_host_address('10.0.0.255/24'), '10.0.0.1')
        self.assertEqual(vyos.template.first_host_address('10.0.0.128/25'), '10.0.0.129')
        self.assertEqual(vyos.template.first_host_address('2001:db8::/64'), '2001:db8::1')
        self.assertEqual(vyos.template.first_host_address('2001:db8::1000/64'), '2001:db8::1')
        self.assertEqual(vyos.template.first_host_address('2001:db8::ffff:ffff:ffff:ffff/64'), '2001:db8::1')

    def test_last_host_address(self):
        self.assertEqual(vyos.template.last_host_address('10.0.0.0/24'), '10.0.0.254')
        self.assertEqual(vyos.template.last_host_address('10.0.0.128/25'), '10.0.0.254')
        self.assertEqual(vyos.template.last_host_address('2001:db8::/64'), '2001:db8::ffff:ffff:ffff:ffff')

    def test_increment_ip(self):
        self.assertEqual(vyos.template.inc_ip('10.0.0.0/24', '2'), '10.0.0.2')
        self.assertEqual(vyos.template.inc_ip('10.0.0.0', '2'), '10.0.0.2')
        self.assertEqual(vyos.template.inc_ip('10.0.0.0', '10'), '10.0.0.10')
        self.assertEqual(vyos.template.inc_ip('2001:db8::/64', '2'), '2001:db8::2')
        self.assertEqual(vyos.template.inc_ip('2001:db8::', '10'), '2001:db8::a')

    def test_decrement_ip(self):
        self.assertEqual(vyos.template.dec_ip('10.0.0.100/24', '1'), '10.0.0.99')
        self.assertEqual(vyos.template.dec_ip('10.0.0.90', '10'), '10.0.0.80')
        self.assertEqual(vyos.template.dec_ip('2001:db8::b/64', '10'), '2001:db8::1')
        self.assertEqual(vyos.template.dec_ip('2001:db8::f', '5'), '2001:db8::a')

    def test_is_network(self):
        self.assertFalse(vyos.template.is_ip_network('192.0.2.0'))
        self.assertFalse(vyos.template.is_ip_network('192.0.2.1/24'))
        self.assertTrue(vyos.template.is_ip_network('192.0.2.0/24'))

        self.assertFalse(vyos.template.is_ip_network('2001:db8::'))
        self.assertFalse(vyos.template.is_ip_network('2001:db8::ffff'))
        self.assertTrue(vyos.template.is_ip_network('2001:db8::/48'))
        self.assertTrue(vyos.template.is_ip_network('2001:db8:1000::/64'))

    def test_is_network(self):
        self.assertTrue(vyos.template.compare_netmask('10.0.0.0/8', '20.0.0.0/8'))
        self.assertTrue(vyos.template.compare_netmask('10.0.0.0/16', '20.0.0.0/16'))
        self.assertFalse(vyos.template.compare_netmask('10.0.0.0/8', '20.0.0.0/16'))
        self.assertFalse(vyos.template.compare_netmask('10.0.0.1', '20.0.0.0/16'))

        self.assertTrue(vyos.template.compare_netmask('2001:db8:1000::/48', '2001:db8:2000::/48'))
        self.assertTrue(vyos.template.compare_netmask('2001:db8:1000::/64', '2001:db8:2000::/64'))
        self.assertFalse(vyos.template.compare_netmask('2001:db8:1000::/48', '2001:db8:2000::/64'))

    def test_cipher_to_string(self):
        ESP_DEFAULT = 'aes256gcm128-sha256-ecp256,aes128ccm64-sha256-ecp256'
        IKEv2_DEFAULT = 'aes256gcm128-sha256-ecp256,aes128ccm128-md5_128-modp1024'

        data = {
            'esp_group': {
                'ESP_DEFAULT': {
                    'compression': 'disable',
                    'lifetime': '3600',
                    'mode': 'tunnel',
                    'pfs': 'dh-group19',
                    'proposal': {
                        '10': {
                            'encryption': 'aes256gcm128',
                            'hash': 'sha256',
                        },
                        '20': {
                            'encryption': 'aes128ccm64',
                            'hash': 'sha256',
                        }
                    }
                }
            },
            'ike_group': {
                'IKEv2_DEFAULT': {
                    'close_action': 'none',
                    'dead_peer_detection': {
                        'action': 'hold',
                        'interval': '30',
                        'timeout': '120'
                    },
                    'ikev2_reauth': 'no',
                    'key_exchange': 'ikev2',
                    'lifetime': '10800',
                    'mobike': 'disable',
                    'proposal': {
                        '10': {
                            'dh_group': '19',
                            'encryption': 'aes256gcm128',
                            'hash': 'sha256'
                        },
                        '20': {
                            'dh_group': '2',
                            'encryption': 'aes128ccm128',
                            'hash': 'md5_128'
                        },
                    }
                }
            },
        }

        for group_name, group_config in data['esp_group'].items():
            ciphers = vyos.template.get_esp_ike_cipher(group_config)
            self.assertIn(ESP_DEFAULT, ','.join(ciphers))

        for group_name, group_config in data['ike_group'].items():
            ciphers = vyos.template.get_esp_ike_cipher(group_config)
            self.assertIn(IKEv2_DEFAULT, ','.join(ciphers))

    def test_get_default_port(self):
        from vyos.defaults import config_files
        from vyos.defaults import internal_ports

        with self.assertRaises(RuntimeError):
            vyos.template.get_default_config_file('UNKNOWN')
        with self.assertRaises(RuntimeError):
            vyos.template.get_default_port('UNKNOWN')
        with self.assertRaises(RuntimeError):
            vyos.template.nft_accept_invalid('UNKNOWN')

        self.assertEqual(vyos.template.get_default_config_file('sshd_user_ca'),
                         config_files['sshd_user_ca'])
        self.assertEqual(vyos.template.get_default_port('certbot_haproxy'),
                         internal_ports['certbot_haproxy'])
        self.assertEqual(vyos.template.nft_accept_invalid('arp'),
                         'ct state invalid ether type arp counter accept')

    def test_decode_rfc3442_routes(self):
        # The destination descriptors from the table in RFC 3442, each paired
        # with a router of 10.17.66.41. The leading descriptor of 0 is the
        # default route, which is retrieved from the router option instead and
        # is therefore not returned here.
        encoded = (
            '0 10 17 66 41 '
            '8 10 10 17 66 41 '
            '24 10 0 0 10 17 66 41 '
            '16 10 17 10 17 66 41 '
            '24 10 27 129 10 17 66 41 '
            '25 10 229 0 128 10 17 66 41 '
            '32 10 198 122 47 10 17 66 41'
        )
        self.assertEqual(
            vyos.template._decode_rfc3442_routes(encoded),
            [
                ('10.0.0.0/8', '10.17.66.41'),
                ('10.0.0.0/24', '10.17.66.41'),
                ('10.17.0.0/16', '10.17.66.41'),
                ('10.27.129.0/24', '10.17.66.41'),
                ('10.229.0.128/25', '10.17.66.41'),
                ('10.198.122.47/32', '10.17.66.41'),
            ],
        )

    def test_decode_rfc3442_routes_on_link(self):
        # An all zero router means the destination is reachable on-link, the
        # route is then installed without a next hop
        self.assertEqual(
            vyos.template._decode_rfc3442_routes('24 172 16 0 0 0 0 0'),
            [('172.16.0.0/24', '')],
        )

    def test_decode_rfc3442_routes_malformed(self):
        # A malformed option is discarded as a whole
        for encoded in [
            '',
            '24 192 168 42',
            '33 1 2 3 4 5 6 7 8',
            '24 192 168 42 192 168 0 250 vyos',
            '24 192 168 300 192 168 0 250',
        ]:
            self.assertEqual(vyos.template._decode_rfc3442_routes(encoded), [])

    def test_decode_rfc3442_routes_host_bits(self):
        # A server may leave host bits set in the final octet of the
        # destination descriptor. The prefix has to be masked, as FRR masks it
        # when accepting the route and the two would otherwise never match.
        self.assertEqual(
            vyos.template._decode_rfc3442_routes('25 129 210 177 132 192 168 0 250'),
            [('129.210.177.128/25', '192.168.0.250')],
        )

    def test_decode_rfc3442_routes_partial(self):
        # A valid route followed by a truncated one discards the option in
        # full, rather than keeping the part that parsed
        encoded = '24 10 0 0 192 0 2 1 24 10 1'
        self.assertEqual(vyos.template._decode_rfc3442_routes(encoded), [])

    def test_decode_rfc3442_routes_default_only(self):
        # An option carrying nothing but a default route yields no routes, the
        # default is retrieved from the router option instead
        self.assertEqual(vyos.template._decode_rfc3442_routes('0 10 17 66 41'), [])
