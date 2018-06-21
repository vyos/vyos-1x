#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
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
#
#

import sys
import subprocess

from vyos.config import Config
from vyos import ConfigError

def get_config():
  conf = Config()
  if not conf.exists('system options beep-if-fully-booted'):
    return 1
  else:
    return 0

def apply(status):
  if status == 1:
    rc = subprocess.call(['/bin/systemctl -q disable beep'], shell=True)
    return rc
  elif status == 0:
    rc = subprocess.call(['/bin/systemctl -q enable beep'], shell=True)
    return rc

if __name__ == '__main__':
  try:
    c = get_config()
    apply(c)
  except ConfigError as e:
    print(e)
    sys.exit(1)
