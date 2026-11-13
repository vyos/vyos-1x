# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

import subprocess
import sys
from unittest import TestCase

validator = 'src/validators/ascii-url'
options = [
    '--scheme',
    'http',
    '--scheme',
    'https',
    '--scheme',
    'ftp',
    '--scheme',
    'ftps',
    '--scheme',
    'tftp',
    '--max-length',
    '255',
]


def valid(url: str) -> bool:
    cmd = [sys.executable, validator] + options + [url]
    return subprocess.run(cmd, capture_output=True, check=False).returncode == 0


class TestAsciiUrlValidator(TestCase):
    def test_valid(self):
        for url in [
            'http://prov.vyos.io/phones/cfg',
            'https://prov.vyos.io:8443/phones?model=$MA',
            'ftp://user:pw@prov.vyos.io/phones',
            'tftp://192.0.2.1/boot',
            'http://[2001:db8::1]:8080/phones',
            'HTTP://prov.vyos.io/',
            # a comma in the query, a query without a path, a fragment
            'http://prov.vyos.io/phones?models=a,b',
            'https://prov.vyos.io?model=$MA',
            'https://prov.vyos.io#cfg',
            # punycode has two hyphens in a row
            'https://xn--bcher-kva.example/',
            'http://prov_1.vyos.io/',
            # an absolute name with the dot of the DNS root
            'http://prov.vyos.io./phones/cfg',
            'https://prov.vyos.io.:8443/phones',
            'tftp://192.0.2.1./boot',
            # a label of 63 characters is the longest one
            'http://' + 'a' * 63 + '.example/boot',
        ]:
            with self.subTest(url=url):
                self.assertTrue(valid(url))

    def test_scheme(self):
        for url in ['file:///etc', 'ssh://prov.vyos.io/', 'prov.vyos.io/cfg']:
            with self.subTest(url=url):
                self.assertFalse(valid(url))

    def test_host(self):
        for url in [
            'http://',
            'http:///etc',
            'https://?x=1',
            'http:/prov.vyos.io',
            'http://-bad.vyos.io/',
            'http://bad-.vyos.io/',
            'http://a..b/',
            # only one dot at the end, and not a name that is only a dot
            'http://prov.vyos.io../',
            'http://a..b./',
            'http://./',
            'http://.prov.vyos.io/',
            'http://999.1.1.1/',
            'http://[zz::1]/',
            # a DNS label is at most 63 characters long
            'http://' + 'a' * 64 + '.example/boot',
        ]:
            with self.subTest(url=url):
                self.assertFalse(valid(url))

    def test_port(self):
        for url in [
            'http://prov.vyos.io:abc/phones',
            'http://prov.vyos.io:/phones',
            'http://prov.vyos.io:0/phones',
            'http://prov.vyos.io:99999/phones',
        ]:
            with self.subTest(url=url):
                self.assertFalse(valid(url))

    def test_ascii_only(self):
        for url in [
            'http://prov.vyos.io/phönes',
            'http://prov-ä.vyos.io/',
            'http://ä',
            'http://prov.vyos.io/phones cfg',
            'http://prov.vyos.io/a\\b',
            'http://prov.vyos.io/a\\,b',
        ]:
            with self.subTest(url=url):
                self.assertFalse(valid(url))

    def test_length(self):
        prefix = 'https://prov.vyos.io/'
        self.assertTrue(valid(prefix + 'a' * (255 - len(prefix))))
        self.assertFalse(valid(prefix + 'a' * (256 - len(prefix))))
