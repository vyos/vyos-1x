#!/usr/bin/env python3
# Copyright 2020-2023 VyOS maintainers and contributors <maintainers@vyos.io>
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
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import argparse
from vyos.utils.process import popen

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--selector', help='Selector: username|ifname|sid', required=True)
    args = parser.parse_args()

    output, err = popen("accel-cmd -p 2002 show sessions {0}".format(args.selector))
    if not err:
        res = output.split("\r\n")
        # Delete header from list
        del res[:2]
        print(' '.join(res))
