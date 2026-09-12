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
from unittest.mock import patch, MagicMock


def _make_psutil_net_conn(ip, port, pid):
    c = MagicMock()
    c.laddr.ip = ip
    c.laddr.port = port
    c.pid = pid
    return c


class TestVyOSUtils(TestCase):
    def test_cmdl_basic(self):
        from vyos.utils.process import cmdl
        out = cmdl(['echo', 'hello'])
        self.assertEqual(out, 'hello')

    def test_cmdl_requires_list(self):
        from vyos.utils.process import cmdl
        with self.assertRaises(TypeError):
            cmdl('echo hello')

    def test_cmdl_sudo_prepends(self):
        from vyos.utils.process import cmdl
        with patch('vyos.utils.process.popen') as mock_popen:
            mock_popen.return_value = ('', 0)
            cmdl(['id'], sudo=True)
            args, kwargs = mock_popen.call_args
            self.assertEqual(args[0][0], 'sudo')
            self.assertEqual(args[0][1], 'id')

    def test_cmdl_no_shell(self):
        from vyos.utils.process import cmdl
        with patch('vyos.utils.process.popen') as mock_popen:
            mock_popen.return_value = ('', 0)
            cmdl(['true'])
            _, kwargs = mock_popen.call_args
            self.assertEqual(kwargs.get('shell'), False)

    def test_cmdl_raises_on_nonzero(self):
        from vyos.utils.process import cmdl
        with self.assertRaises(OSError):
            cmdl(['false'])
    def test_key_mangling(self):
        from vyos.utils.dict import mangle_dict_keys
        data = {"foo-bar": {"baz-quux": None}}
        expected_data = {"foo_bar": {"baz_quux": None}}
        new_data = mangle_dict_keys(data, '-', '_')
        self.assertEqual(new_data, expected_data)

    def test_sysctl_read(self):
        from vyos.utils.system import sysctl_read
        self.assertEqual(sysctl_read(['net', 'ipv4', 'conf', 'lo', 'forwarding']), '1')

    def test_sysctl_key_normalization(self):
        from vyos.utils.system import sysctl_read
        with patch('vyos.utils.system.run') as mock_run:
            mock_run.return_value.stdout = b'1\n'
            sysctl_read(['net', 'ipv4', 'conf', 'eth0.10', 'forwarding'])
            mock_run.assert_called_with(
                ['sysctl', '-nb', 'net.ipv4.conf.eth0/10.forwarding'],
                capture_output=True,
            )

    def test_list_strip(self):
        from vyos.utils.list import list_strip

        lst = ['a', 'b', 'c', 'd', 'e']
        sub = ['a', 'b']
        rsb = ['d', 'e']
        non = ['a', 'e']
        self.assertEqual(list_strip(lst, sub), ['c', 'd', 'e'])
        self.assertEqual(list_strip(lst, rsb, right=True), ['a', 'b', 'c'])
        self.assertEqual(list_strip(lst, non), [])
        self.assertEqual(list_strip(sub, lst), [])

    def test_range_str_to_list(self):
        from vyos.utils.convert import range_str_to_list

        # basic cases
        self.assertEqual(range_str_to_list('1-3'), [1, 2, 3])
        self.assertEqual(range_str_to_list('1-3,5,7-8'), [1, 2, 3, 5, 7, 8])
        self.assertEqual(range_str_to_list('3'), [3])
        # empty string
        self.assertEqual(range_str_to_list(''), [])
        # unordered input
        self.assertEqual(range_str_to_list('5,1-3,4'), [1, 2, 3, 4, 5])
        self.assertEqual(range_str_to_list('7-9,1-3'), [1, 2, 3, 7, 8, 9])
        # overlapping ranges
        self.assertEqual(range_str_to_list('1-5,3-7'), [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(range_str_to_list('1-3,2-4,3-5'), [1, 2, 3, 4, 5])
        # duplicated values
        self.assertEqual(range_str_to_list('1,1,2,2,3'), [1, 2, 3])
        self.assertEqual(range_str_to_list('5,1-3,2,3'), [1, 2, 3, 5])
        # adjacent ranges
        self.assertEqual(range_str_to_list('1-3,4-6'), [1, 2, 3, 4, 5, 6])

    def test_list_to_range_str(self):
        from vyos.utils.convert import list_to_range_str

        # basic cases
        self.assertEqual(list_to_range_str([1, 2, 3]), '1-3')
        self.assertEqual(list_to_range_str([1, 2, 3, 5, 7, 8]), '1-3,5,7-8')
        self.assertEqual(list_to_range_str([1, 3]), '1,3')
        self.assertEqual(list_to_range_str([3]), '3')
        # empty list
        self.assertEqual(list_to_range_str([]), '')
        # unordered input
        self.assertEqual(list_to_range_str([5, 1, 2, 3, 4]), '1-5')
        self.assertEqual(list_to_range_str([7, 8, 9, 1, 2, 3]), '1-3,7-9')
        # duplicated values
        self.assertEqual(list_to_range_str([1, 1, 2, 2, 3, 3]), '1-3')
        self.assertEqual(list_to_range_str([5, 1, 2, 2, 3, 5]), '1-3,5')

    def test_is_addr_assigned_nonlocal_bind_ipv4(self):
        """When net.ipv4.ip_nonlocal_bind=1, any valid IPv4 must return True."""
        from vyos.utils.network import is_addr_assigned

        with patch('vyos.utils.network.sysctl_read', return_value='1'):
            self.assertTrue(is_addr_assigned('192.0.2.99', allow_nonlocal=True))

    def test_is_addr_assigned_nonlocal_bind_ipv6(self):
        from vyos.utils.network import is_addr_assigned

        with patch('vyos.utils.network.sysctl_read', return_value='1'):
            self.assertTrue(is_addr_assigned('2001:db8::1', allow_nonlocal=True))

    def test_is_addr_assigned_nonlocal_bind_ipv4_off_unassigned(self):
        """When sysctl is 0 and address is not assigned, must return False."""
        from vyos.utils.network import is_addr_assigned

        with patch('vyos.utils.network.sysctl_read', return_value='0'), patch(
            'netifaces.interfaces', return_value=[]
        ):
            self.assertFalse(is_addr_assigned('192.0.2.99', allow_nonlocal=True))

    def test_is_addr_assigned_nonlocal_bind_ipv6_off_unassigned(self):
        """When sysctl is 0 and address is not assigned, must return False."""
        from vyos.utils.network import is_addr_assigned

        with patch('vyos.utils.network.sysctl_read', return_value='0'), patch(
            'netifaces.interfaces', return_value=[]
        ):
            self.assertFalse(is_addr_assigned('2001:db8::1', allow_nonlocal=True))

    def test_is_addr_assigned_vrf_filter(self):
        """Address on a VRF slave should only match when vrf matches."""
        from vyos.utils.network import is_addr_assigned

        iface_cfg_red = {'master': 'red'}
        iface_cfg_lo = {'master': None}  # loopback has no master

        with patch('vyos.utils.network.sysctl_read', return_value='0'), patch(
            'netifaces.interfaces', return_value=['lo', 'eth0']
        ), patch(
            'vyos.utils.network.get_interface_config',
            side_effect=[iface_cfg_lo, iface_cfg_red],
        ), patch(
            'vyos.utils.network.is_intf_addr_assigned', return_value=True
        ) as mock_is_assigned:
            # vrf='red' → should find it on eth0
            self.assertTrue(
                is_addr_assigned('10.0.0.1', vrf='red', allow_nonlocal=True)
            )
            mock_is_assigned.assert_called_once_with('eth0', '10.0.0.1')

    def test_is_addr_assigned_wrong_vrf(self):
        """Address on VRF 'red' must not match when querying vrf='blue'."""
        from vyos.utils.network import is_addr_assigned

        iface_cfg = {'master': 'red'}
        with patch('vyos.utils.network.sysctl_read', return_value='0'), patch(
            'netifaces.interfaces', return_value=['eth0']
        ), patch(
            'vyos.utils.network.get_interface_config', return_value=iface_cfg
        ), patch(
            'vyos.utils.network.is_intf_addr_assigned', return_value=True
        ):
            self.assertFalse(
                is_addr_assigned('10.0.0.1', vrf='blue', allow_nonlocal=True)
            )

    def test_is_listen_port_wildcard_ipv4(self):
        """Service on 0.0.0.0 must match even when a specific address filter is given."""
        from vyos.utils.network import is_listen_port_bind_service

        conn = _make_psutil_net_conn('0.0.0.0', 443, 1234)
        with patch('psutil.net_connections', return_value=[conn]), patch(
            'psutil.Process'
        ) as MockProc:
            MockProc.return_value.name.return_value = 'haproxy'
            self.assertTrue(
                is_listen_port_bind_service(443, 'haproxy', address='194.0.2.1')
            )

    def test_is_listen_port_wildcard_ipv6(self):
        """Service on :: must match even when an address filter is given."""
        from vyos.utils.network import is_listen_port_bind_service

        conn = _make_psutil_net_conn('::', 443, 1234)
        with patch('psutil.net_connections', return_value=[conn]), patch(
            'psutil.Process'
        ) as MockProc:
            MockProc.return_value.name.return_value = 'haproxy'
            self.assertTrue(
                is_listen_port_bind_service(443, 'haproxy', address='2001:db8::1')
            )

    def test_is_listen_port_specific_address_match(self):
        """Service on specific IP must match only the exact address."""
        from vyos.utils.network import is_listen_port_bind_service

        conn = _make_psutil_net_conn('194.0.2.1', 443, 1234)
        with patch('psutil.net_connections', return_value=[conn]), patch(
            'psutil.Process'
        ) as MockProc:
            MockProc.return_value.name.return_value = 'haproxy'
            self.assertTrue(
                is_listen_port_bind_service(443, 'haproxy', address='194.0.2.1')
            )
            self.assertFalse(
                is_listen_port_bind_service(443, 'haproxy', address='10.0.0.1')
            )
