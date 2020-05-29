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
import re
import syslog as sl

from vyos.config import Config
from vyos.util import call
from vyos import ConfigError

from vyos import airbag
airbag.enable()

arp_cmd = '/usr/sbin/arp'

def get_config():
  c = Config()
  if not c.exists('protocols static arp'):
    return None

  c.set_level('protocols static')
  config_data = {}
  
  for ip_addr in c.list_nodes('arp'):
    config_data.update(
        {
          ip_addr : c.return_value('arp ' + ip_addr + ' hwaddr')
        }
    )

  return config_data

def generate(c):
  c_eff = Config()
  c_eff.set_level('protocols static')
  c_eff_cnf = {}
  for ip_addr in c_eff.list_effective_nodes('arp'):
    c_eff_cnf.update(
        {
          ip_addr : c_eff.return_effective_value('arp ' + ip_addr + ' hwaddr')
        }
    )

  config_data = {
    'remove'  : [],
    'update'  : {}
  }
  ### removal
  if c == None:
    for ip_addr in c_eff_cnf:
      config_data['remove'].append(ip_addr)
  else:
    for ip_addr in c_eff_cnf:
      if not ip_addr in c or c[ip_addr] == None:
        config_data['remove'].append(ip_addr)

  ### add/update
  if c != None:
    for ip_addr in c:
      if not ip_addr in c_eff_cnf:
        config_data['update'][ip_addr] = c[ip_addr]
      if  ip_addr in c_eff_cnf:
        if c[ip_addr] != c_eff_cnf[ip_addr] and c[ip_addr] != None:
          config_data['update'][ip_addr] = c[ip_addr]

  return config_data

def apply(c):
  for ip_addr in c['remove']:
    sl.syslog(sl.LOG_NOTICE, "arp -d " + ip_addr)
    call(f'{arp_cmd} -d {ip_addr} >/dev/null 2>&1')

  for ip_addr in c['update']:
    sl.syslog(sl.LOG_NOTICE, "arp -s " + ip_addr + " " + c['update'][ip_addr])
    updated = c['update'][ip_addr]
    call(f'{arp_cmd} -s {ip_addr} {updated}')


if __name__ == '__main__':
  try:
    c = get_config()
    ## syntax verification is done via cli
    config = generate(c)
    apply(config)
  except ConfigError as e:
    print(e)
    sys.exit(1)
