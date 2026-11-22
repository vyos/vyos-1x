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

from unittest import TestCase

from vyos.kea import kea_parse_options
from vyos.kea import kea6_parse_options

NODES = {
    'tftp_server_name': 'tftp-server-name',
    'bootfile_name': 'boot-file-name',
    'wpad_url': 'wpad-url',
    'captive_portal': 'v4-captive-portal',
}


def data_of(node: str, value: str) -> str:
    return kea_parse_options({node: value})[0]['data']


class TestKeaStringOptions(TestCase):
    def test_bare_comma_is_escaped(self):
        for node, name in NODES.items():
            with self.subTest(node=node):
                options = kea_parse_options({node: 'http://host/p?a,b,c'})
                self.assertEqual(
                    options, [{'name': name, 'data': 'http://host/p?a\\,b\\,c'}]
                )

    def test_value_without_comma_is_unchanged(self):
        for node in NODES:
            with self.subTest(node=node):
                self.assertEqual(
                    data_of(node, 'http://host/p?a=b'), 'http://host/p?a=b'
                )

    def test_existing_escape_sequences_stay(self):
        for value, expected in [
            # an escaped comma is not escaped again
            ('a\\,b', 'a\\,b'),
            # a backslash that is not followed by a comma
            ('boot\\x64\\file', 'boot\\x64\\file'),
            ('a\\', 'a\\'),
            ('\\', '\\'),
            ('', ''),
            (',', '\\,'),
            # an escaped backslash does not escape the comma behind it
            ('a\\\\,b', 'a\\\\\\,b'),
            # both in one value
            ('boot\\x64\\file,a\\,b', 'boot\\x64\\file\\,a\\,b'),
        ]:
            for node in NODES:
                with self.subTest(node=node, value=value):
                    self.assertEqual(data_of(node, value), expected)

    def test_list_separator_is_not_escaped(self):
        # the comma between the entries of a list is meant for Kea
        options = kea_parse_options({'time_server': ['192.0.2.1', '192.0.2.2']})
        self.assertEqual(
            options, [{'name': 'time-servers', 'data': '192.0.2.1, 192.0.2.2'}]
        )

    def test_dhcpv6_captive_portal(self):
        # the DHCPv6 option is a string as well, the other options are not touched
        options = kea6_parse_options(
            {
                'captive_portal': 'https://host/api?a,b,c\\,d',
                'name_server': ['2001:db8::1', '2001:db8::2'],
            }
        )
        self.assertEqual(
            options,
            [
                {'name': 'dns-servers', 'data': '2001:db8::1, 2001:db8::2'},
                {'name': 'v6-captive-portal', 'data': 'https://host/api?a\\,b\\,c\\,d'},
            ],
        )
