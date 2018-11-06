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
import os
import subprocess
import re
import itertools
from datetime import datetime, timedelta

verf = r'/usr/libexec/vyos/op_mode/version.py'

def get_sys_build_version():
  if not os.path.exists(verf):
    return None

  a = subprocess.check_output(['/usr/libexec/vyos/op_mode/version.py']).decode()
  if re.search('^Built on:.+',a, re.M) == None:
    return None

  dt = ( re.sub('Built on: +','', re.search('^Built on:.+',a, re.M).group(0)) )
  return datetime.strptime(dt,'%a %d %b %Y %H:%M %Z')

def check_pkgs(dt):
  pkg_diffs = {
    'buildtime' : str(dt),
    'pkg'  : {}
  }

  pkg_info = os.listdir('/var/lib/dpkg/info/')
  for file in pkg_info:
    if re.search('\.list$', file):
      fts = os.stat('/var/lib/dpkg/info/' + file).st_mtime
      dt_str = (datetime.utcfromtimestamp(fts).strftime('%Y-%m-%d %H:%M:%S'))
      fdt =  datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
      if fdt > dt:
        pkg_diffs['pkg'].update( { str(re.sub('\.list','',file)) : str(fdt)})

  if len(pkg_diffs['pkg']) != 0:
    return pkg_diffs
  else:
    return None

def main():
  dt = get_sys_build_version()
  pkgs = check_pkgs(dt)
  if pkgs != None:
    print ("The following packages don\'t fit the image creation time\nbuild time:\t" + pkgs['buildtime'])
    for k, v in pkgs['pkg'].items():
      print ("installed: " + v + '\t' + k)

if __name__ == '__main__':
  sys.exit( main() )

