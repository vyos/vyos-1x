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

import pathlib
import shutil
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.defaults import directories
from vyos.utils.process import cmd

base_path = ['show tech-support report']
script_path = directories['op_mode'] + '/show_techsupport_report.py'
testdir = pathlib.Path('/tmp/_test_techsupport_report')

all_blocks = (
    'vyos-main-info',
    'routing-info',
    'frr-info',
    'proc-and-sysctl-info',
    'net-and-processes-info',
    'ethtool-info',
    'lspci-and-numa-info',
    'nftables-info',
    'dpkg-and-modules-info',
    'system-resources-info',
    'ipsec-debug-info',
    'vpp-info',
)


class TestTechSupportReport(VyOSUnitTestSHIM.TestCase):
    def _gen_section_header(self, name: str) -> str:
        length = len(name)
        return '=' * length + '\n' + name + '\n' + '=' * length + '\n'

    def assertSectionIn(self, name: str, report: str):
        header = self._gen_section_header(name)
        self.assertIn(header, report, f'Report does not contain section `{name}`')

    def assertSectionNotIn(self, name: str, report: str):
        header = self._gen_section_header(name)
        self.assertNotIn(
            header, report, f'Report contains unnecessary section `{name}`'
        )

    def test_full_report(self):
        report = self.op_mode(base_path)
        for block in all_blocks:
            self.assertSectionIn(block, report)

    def test_filtered_report(self):
        blocks = (
            'vyos-main-info',
            'proc-and-sysctl-info',
        )

        report = cmd([script_path, '--reports'] + list(blocks))

        for block in blocks:
            self.assertSectionIn(block, report)

        missing_blocks = frozenset(all_blocks) - frozenset(blocks)
        for block in missing_blocks:
            self.assertSectionNotIn(block, report)

    def test_directory_output(self):
        cmd([script_path, '--outdir', str(testdir)])

        for block in all_blocks:
            file_path = testdir / block
            err_message = f'File `{file_path}` does not exist after generating a report'

            self.assertTrue(file_path.exists(), err_message)
            self.assertSectionIn(block, file_path.read_text())

        shutil.rmtree(testdir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
