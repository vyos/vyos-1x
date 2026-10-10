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
import shutil
import tempfile
import unittest
from glob import glob

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configtree import ConfigTree
from vyos.utils.file import read_file
from vyos.utils.kernel import check_kmod
from vyos.utils.network import interface_exists
from vyos.utils.process import call
from vyos.utils.process import rc_cmd

rescan = '/usr/libexec/vyos/vyos-interface-rescan.py'
rescan_log = '/var/log/vyatta/vyos-interface-rescan'

class WirelessRescanTest(VyOSUnitTestSHIM.TestCase):
    """T3871: a radio is not in the interface mapping file - every interface on
    a phy carries that phy's address, so there is nothing there to anchor a
    name to. The rescan has to find radios on the system instead. While it took
    its whole list from the map, no radio was ever given a node and 'interfaces
    wireless' stayed empty on a box which had one.
    """

    ifname = 'wlan99'

    def setUp(self):
        phys = sorted(os.path.basename(p)
                      for p in glob('/sys/class/ieee80211/*'))
        if not phys:
            self.skipTest('no wireless phy on this system')
        self.phy = phys[0]

        # an interface of our own, so the test does not depend on which radios
        # another testcase left behind
        if interface_exists(self.ifname):
            call(f'sudo iw dev {self.ifname} del')
        if call(f'sudo iw phy {self.phy} interface add {self.ifname} '
                'type managed') != 0:
            self.skipTest(f'could not create an interface on {self.phy}')
        self.addCleanup(call, f'sudo iw dev {self.ifname} del')

    def test_a_radio_is_given_its_physical_device(self):
        # a directory of our own, not /tmp itself - the rescan runs as root
        # and fs.protected_regular refuses it an O_CREAT on a file it does not
        # own in a world writable sticky directory
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        tmp = os.path.join(tmp_dir, 'config.boot')
        shutil.copy('/config/config.boot', tmp)

        config = ConfigTree(read_file(tmp))
        self.assertFalse(config.exists(['interfaces', 'wireless', self.ifname]))

        rc, out = rc_cmd(f'sudo {rescan} {tmp}')
        if rc != 0:
            # it reports a failure to its own log rather than to stderr, so
            # without this a failure here is just an exit code
            _, log = rc_cmd(f'sudo tail -n 20 {rescan_log}')
            self.fail(f'rescan exited {rc}: {out}\n{log}')

        config = ConfigTree(read_file(tmp))
        self.assertTrue(config.exists(['interfaces', 'wireless', self.ifname]))
        self.assertEqual(
            config.return_value(['interfaces', 'wireless', self.ifname,
                                 'physical-device']), self.phy)

if __name__ == '__main__':
    check_kmod('mac80211_hwsim')
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
