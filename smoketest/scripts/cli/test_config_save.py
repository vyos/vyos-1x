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

import os
import unittest

from vyos.utils.process import cmd
from vyos.utils.config import read_saved_value
from vyos.defaults import directories

from base_vyostest_shim import VyOSUnitTestSHIM

class TestConfigDep(VyOSUnitTestSHIM.TestCase):
    def test_disk_resident(self):
        config_file = os.path.join(directories['config'], 'config.boot')

        evict_cmd = f'vmtouch -e {config_file}'
        page_count_cmd = f'fincore -o PAGES -n {config_file}'

        test_value = 'test_disk_resident'
        test_path = ['interfaces', 'ethernet', 'eth3', 'description']

        self.cli_set(test_path, value=test_value)
        self.cli_commit()
        self.cli_save(config_file)

        cmd(evict_cmd)
        # pages may be paged back into memory by the time the above
        # completes (man vmtouch); either way, we read what is resident on
        # disk. The following is just for curiosity:
        pages = cmd(page_count_cmd)

        saved_value = read_saved_value(test_path)

        if self.debug:
            print(f'vm pages on read config: {int(pages)}')

        self.assertEqual(test_value, saved_value)

        # clean up remaining
        self.cli_delete(test_path)
        self.cli_commit()
        self.cli_save(config_file)

    def test_disk_resident_atomic(self):
        config_file = os.path.join(directories['config'], 'config.boot')

        # save config will only call write_file_atomic if euid == 0:
        # below is the command as invoked by CLI 'save'
        save_cmd = (
            'sudo sg vyattacfg "umask 0002; /usr/libexec/vyos/vyos-save-config.py"'
        )

        evict_cmd = f'vmtouch -e {config_file}'
        page_count_cmd = f'fincore -o PAGES -n {config_file}'

        test_value = 'test_disk_resident'
        test_path = ['interfaces', 'ethernet', 'eth3', 'description']

        self.cli_set(test_path, value=test_value)
        self.cli_commit()
        cmd(save_cmd)

        cmd(evict_cmd)
        # pages may be paged back into memory by the time the above
        # completes (man vmtouch); either way, we read what is resident on
        # disk. The following is just for curiosity:
        pages = cmd(page_count_cmd)

        saved_value = read_saved_value(test_path)

        if self.debug:
            print(f'vm pages on read config: {int(pages)}')

        # check that we have at the least sync'd config;
        # checking actual atomicity is a different matter ...
        self.assertEqual(test_value, saved_value)

        # clean up remaining
        self.cli_delete(test_path)
        self.cli_commit()
        cmd(save_cmd)


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
