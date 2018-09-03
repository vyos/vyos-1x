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
import subprocess

from vyos.config import Config
from vyos import ConfigError

dir = r'/config/auth/wireguard'
pk = dir + '/private.key'
pub = dir + '/public.key'
psk_file = r'/tmp/psk'

def check_kmod():
  if not os.path.exists('/sys/module/wireguard'):
    sl.syslog(sl.LOG_NOTICE, "loading wirguard kmod")
    if  os.system('sudo modprobe wireguard') != 0:
      sl.syslog(sl.LOG_NOTICE, "modprobe wireguard failed")
      raise ConfigError("modprobe wireguard failed")

def get_config():
  c = Config()
  if not c.exists('interfaces wireguard'):
    return None

  c.set_level('interfaces')
  intfcs = c.list_nodes('wireguard')
  intfcs_eff = c.list_effective_nodes('wireguard')
  new_lst = list(set(intfcs) - set(intfcs_eff))
  del_lst = list(set(intfcs_eff) - set(intfcs))

  config_data = {
      'interfaces' : {}
  }
  ### setting defaults and determine status of the config
  for intfc in intfcs:
    cnf = 'wireguard ' + intfc
    # default data struct
    config_data['interfaces'].update(
        {
            intfc : {
                'addr'        : '',
                'descr'       : intfc, ## snmp ifAlias
                'lport'       : '',
                'status'      : 'exists',
                'state'       : 'enabled',
                'mtu'         : '1420',
                'peer'        : {}
            }
        }
    )

  ### determine status either delete or create
  for i in new_lst:
    config_data['interfaces'][i]['status'] = 'create'

  for i in del_lst:
    config_data['interfaces'].update(
        {
            i : {
                'status': 'delete'
            }
        }
    )

  ### based on the status, setup conf values
  for intfc in intfcs:
    cnf = 'wireguard ' + intfc
    if config_data['interfaces'][intfc]['status'] != 'delete':
      ### addresses
      if c.exists(cnf + ' address'):
        config_data['interfaces'][intfc]['addr'] = c.return_values(cnf + ' address')
      ### listen port
      if c.exists(cnf + ' port'):
        config_data['interfaces'][intfc]['lport'] = c.return_value(cnf + ' port')
      ### description
      if c.exists(cnf + ' description'):
        config_data['interfaces'][intfc]['descr'] = c.return_value(cnf + ' description')
      ### mtu
      if c.exists(cnf + ' mtu'):
        config_data['interfaces'][intfc]['mtu'] = c.return_value(cnf + ' mtu')
      ### peers
      if c.exists(cnf + ' peer'):
        for p in c.list_nodes(cnf + ' peer'):
          config_data['interfaces'][intfc]['peer'].update(
              {
                  p : {
                      'allowed-ips' : [],
                      'endpoint'  : '',
                      'pubkey'  : ''
                  }
              }
          )
          if c.exists(cnf + ' peer ' + p + ' pubkey'):
            config_data['interfaces'][intfc]['peer'][p]['pubkey'] = c.return_value(cnf + ' peer ' + p + ' pubkey')
          if c.exists(cnf + ' peer ' + p + ' allowed-ips'):
            config_data['interfaces'][intfc]['peer'][p]['allowed-ips'] = c.return_values(cnf + ' peer ' + p + ' allowed-ips')
          if c.exists(cnf + ' peer ' + p + ' endpoint'):
            config_data['interfaces'][intfc]['peer'][p]['endpoint'] = c.return_value(cnf + ' peer ' + p + ' endpoint')
          if c.exists(cnf + ' peer ' + p + ' persistent-keepalive'):
            config_data['interfaces'][intfc]['peer'][p]['persistent-keepalive'] = c.return_value(cnf + ' peer ' + p + ' persistent-keepalive')
          if c.exists(cnf + ' peer ' + p + ' preshared-key'):
            config_data['interfaces'][intfc]['peer'][p]['psk'] = c.return_value(cnf + ' peer ' + p + ' preshared-key')
  
  return config_data

def verify(c):
  if not c:
    return None

  for i in c['interfaces']:
    if c['interfaces'][i]['status'] != 'delete':
      if not c['interfaces'][i]['addr']:
        raise ConfigError("address required for interface " + i)
      if not c['interfaces'][i]['peer']:
        raise ConfigError("peer required on interface " + i)

      for p in c['interfaces'][i]['peer']:
        if not c['interfaces'][i]['peer'][p]['allowed-ips']:
          raise ConfigError("allowed-ips required on interface " + i + " for peer " + p)
        if not c['interfaces'][i]['peer'][p]['pubkey']:
          raise ConfigError("pubkey from your peer is mandatory on " + i + " for peer " + p)


def apply(c):
  ### no wg config left, delete all wireguard devices on the os
  if not c:
    net_devs = os.listdir('/sys/class/net/')
    for dev in net_devs:
      buf = open('/sys/class/net/' + dev + '/uevent', 'r').read()
      if re.search("DEVTYPE=wireguard", buf, re.I|re.M):
        wg_intf = re.sub("INTERFACE=", "", re.search("INTERFACE=.*", buf, re.I|re.M).group(0))
        sl.syslog(sl.LOG_NOTICE, "removing interface " + wg_intf)
        subprocess.call(['ip l d dev ' + wg_intf + ' >/dev/null'], shell=True)
    return None

  ###
  ## find the diffs between effective config an new config
  ###
  c_eff = Config()
  c_eff.set_level('interfaces wireguard')

  ### deletion of specific interface
  for intf in c['interfaces']:
    if c['interfaces'][intf]['status'] == 'delete':
      sl.syslog(sl.LOG_NOTICE, "removing interface " + intf)
      subprocess.call(['ip l d dev ' + intf + ' &>/dev/null'], shell=True)

    ### new config
    if c['interfaces'][intf]['status'] == 'create':
      if not os.path.exists(pk):
        raise ConfigError("No keys found, generate them by executing: \'run generate wireguard keypair\'")

      subprocess.call(['ip l a dev ' + intf + ' type wireguard 2>/dev/null'], shell=True)
      for addr in c['interfaces'][intf]['addr']:
        add_addr(intf, addr)

      subprocess.call(['ip l set up dev ' + intf + ' mtu ' + c['interfaces'][intf]['mtu'] + ' &>/dev/null'], shell=True)
      configure_interface(c, intf)

    ### config updates
    if c['interfaces'][intf]['status'] == 'exists':
      ### IP address change
      addr_eff = re.sub("\'", "", c_eff.return_effective_values(intf + ' address')).split()
      addr_rem = list(set(addr_eff) - set(c['interfaces'][intf]['addr']))
      addr_add = list(set(c['interfaces'][intf]['addr']) - set(addr_eff))

      if len(addr_rem) != 0:
        for addr in addr_rem:
          del_addr(intf, addr)

      if len(addr_add) != 0:
        for addr in addr_add:
          add_addr(intf, addr)

      ## mtu update
      mtu = c['interfaces'][intf]['mtu']
      if mtu != 1420:
        sl.syslog(sl.LOG_NOTICE, "setting mtu to " + mtu + " on " + intf)
        subprocess.call(['ip l set mtu ' + mtu + ' dev ' + intf + ' &>/dev/null'], shell=True)

      ### persistent-keepalive
      for p in c_eff.list_nodes(intf + ' peer'):
        val_eff = ""
        val = ""

        if c_eff.exists_effective(intf + ' peer ' + p + ' persistent-keepalive'):
          val_eff = c_eff.return_effective_value(intf + ' peer ' + p + ' persistent-keepalive')

        if 'persistent-keepalive' in c['interfaces'][intf]['peer'][p]:
          val = c['interfaces'][intf]['peer'][p]['persistent-keepalive']

        ### disable keepalive
        if val_eff and not val:
          c['interfaces'][intf]['peer'][p]['persistent-keepalive'] = 0

        ### set new keepalive value
        if not val_eff and val:
          c['interfaces'][intf]['peer'][p]['persistent-keepalive'] = val

      ## wg command call
      configure_interface(c, intf)

    ### ifalias for snmp from description
    descr_eff = c_eff.return_effective_value(intf + ' description')
    cnf_descr = c['interfaces'][intf]['descr']
    if descr_eff != cnf_descr:
      with open('/sys/class/net/' + str(intf) + '/ifalias', 'w') as fh:
        fh.write(str(cnf_descr))

def configure_interface(c, intf):
  for p in c['interfaces'][intf]['peer']:
    ## config init for wg call
    wg_config = {
      'interface'   : intf,
      'port'        : 0,
      'private-key' : pk,
      'pubkey'      : '',
      'psk'         : '/dev/null',
      'allowed-ips' : [],
      'fwmark'      : 0x00,
      'endpoint'    : None,
      'keepalive'   : 0
  }

    ## mandatory settings
    wg_config['pubkey'] = c['interfaces'][intf]['peer'][p]['pubkey']
    wg_config['allowed-ips'] = c['interfaces'][intf]['peer'][p]['allowed-ips']

    ## optional settings
    # listen-port
    if c['interfaces'][intf]['lport']:
      wg_config['port'] = c['interfaces'][intf]['lport']

    ## endpoint
    if c['interfaces'][intf]['peer'][p]['endpoint']:
      wg_config['endpoint'] = c['interfaces'][intf]['peer'][p]['endpoint']

    ## persistent-keepalive
    if 'persistent-keepalive' in c['interfaces'][intf]['peer'][p]:
      wg_config['keepalive'] = c['interfaces'][intf]['peer'][p]['persistent-keepalive']

    ## preshared-key - is only read from a file, it's called via sudo redirection doesn't work either
    if 'psk' in c['interfaces'][intf]['peer'][p]:
      old_umask = os.umask(0o077)
      open(psk_file, 'w').write(str(c['interfaces'][intf]['peer'][p]['psk']))
      os.umask(old_umask)
      wg_config['psk'] = psk_file

    ### assemble wg command
    cmd = "sudo wg set " + intf
    cmd += " listen-port " + str(wg_config['port'])
    cmd += " private-key " + wg_config['private-key']
    cmd += " peer " + wg_config['pubkey']
    cmd += " preshared-key " + wg_config['psk']
    cmd += " allowed-ips "
    for ap in wg_config['allowed-ips']:
      if ap != wg_config['allowed-ips'][-1]:
        cmd += ap + ","
      else:
        cmd += ap

    if wg_config['endpoint']:
      cmd += " endpoint " + wg_config['endpoint']

    if wg_config['keepalive'] != 0:
      cmd += " persistent-keepalive " + wg_config['keepalive']
    else:
      cmd += " persistent-keepalive 0"

    sl.syslog(sl.LOG_NOTICE, cmd)
    #print (cmd)
    subprocess.call([cmd], shell=True)
    """ remove psk_file """
    if os.path.exists(psk_file):
      os.remove(psk_file)

def add_addr(intf, addr):
  ret = subprocess.call(['ip a a dev ' + intf + ' ' + addr + ' &>/dev/null'], shell=True)
  if ret != 0:
    raise ConfigError('Can\'t set IP ' + addr + ' on ' + intf)
  else:
    sl.syslog(sl.LOG_NOTICE, "ip a a dev " + intf + " " + addr)

def del_addr(intf, addr):
  ret = subprocess.call(['ip a d dev ' + intf + ' ' + addr + ' &>/dev/null'], shell=True)
  if ret != 0:
    raise ConfigError('Can\'t delete IP ' + addr + ' on ' + intf)
  else:
    sl.syslog(sl.LOG_NOTICE, "ip a d dev " + intf + " " + addr)

if __name__ == '__main__':
  try:
    check_kmod()
    c = get_config()
    verify(c)
    apply(c)
  except ConfigError as e:
    print(e)
    sys.exit(1)
