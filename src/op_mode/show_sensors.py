#!/usr/bin/env python3
#
# Copyright 2017-2023 VyOS maintainers and contributors <maintainers@vyos.io>
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

import re
import sys
from vyos.utils.process import popen
from vyos.utils.process import DEVNULL

output,retcode = popen("sensors --no-adapter",  stderr=DEVNULL)
if retcode == 0:
    print (output)
    sys.exit(0)
else:
    output,retcode = popen("sensors-detect --auto",stderr=DEVNULL)
    match = re.search(r'#----cut here----(.*)#----cut here----',output, re.DOTALL)
    if match:
        for module in match.group(0).split('\n'):
            if not module.startswith("#"):
                popen("modprobe {}".format(module.strip()))
                output,retcode = popen("sensors --no-adapter",  stderr=DEVNULL)
                if retcode == 0:
                    print (output)
                    sys.exit(0)


print ("No sensors found")
sys.exit(1)
