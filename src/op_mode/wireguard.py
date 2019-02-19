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

import argparse
import os
import sys
import subprocess
import syslog as sl

from vyos import ConfigError

dir = r'/config/auth/wireguard'
pk  = dir + '/private.key'
pub = dir + '/public.key'
psk = dir + '/preshared.key'

def check_kmod():
  """ check if kmod is loaded, if not load it """
  if not os.path.exists('/sys/module/wireguard'):
    sl.syslog(sl.LOG_NOTICE, "loading wirguard kmod") 
    if  os.system('sudo modprobe wireguard') != 0:
      sl.syslog(sl.LOG_ERR, "modprobe wireguard failed")
      raise ConfigError("modprobe wireguard failed")

def generate_keypair():
  """ generates a keypair which is stored in /config/auth/wireguard """
  ret = subprocess.call(['wg genkey | tee ' + pk + '|wg pubkey > ' + pub], shell=True)
  if ret != 0:
    raise ConfigError("wireguard key-pair generation failed")
  else:
    sl.syslog(sl.LOG_NOTICE, "new keypair wireguard key generated in " + dir)

def genkey():
  """ helper function to check, regenerate the keypair """
  old_umask = os.umask(0o077)
  if os.path.exists(pk) and os.path.exists(pub):
    try:
      choice = input("You already have a wireguard key-pair already, do you want to re-generate? [y/n] ")
      if choice == 'y' or choice == 'Y':
        generate_keypair()
    except KeyboardInterrupt:
        sys.exit(0)
  else:
    """ if keypair is bing executed from a running iso """
    if not os.path.exists(dir):
      os.umask(old_umask)
      subprocess.call(['sudo mkdir -p ' + dir], shell=True)
      subprocess.call(['sudo chgrp vyattacfg ' + dir], shell=True)
      subprocess.call(['sudo chmod 770 ' + dir], shell=True)
    generate_keypair()
  os.umask(old_umask)

def showkey(key):
  """ helper function to show privkey or pubkey """
  if key == "pub":
    if os.path.exists(pub):
      print ( open(pub).read().strip() )
    else:
      print("no public key found")

  if key == "pk":
    if os.path.exists(pk):
      print ( open(pk).read().strip() )
    else:
      print("no private key found")

def genpsk():
  """ generates a preshared key and shows it on stdout, it's stroed only in the config """
  subprocess.call(['wg genpsk'], shell=True)

if __name__ == '__main__':
  check_kmod()

  parser = argparse.ArgumentParser(description='wireguard key management')
  parser.add_argument('--genkey', action="store_true", help='generate key-pair')
  parser.add_argument('--showpub', action="store_true", help='shows public key')
  parser.add_argument('--showpriv', action="store_true", help='shows private key')
  parser.add_argument('--genpsk', action="store_true", help='generates preshared-key')
  args = parser.parse_args()

  try:
    if args.genkey:
      genkey()
    if args.showpub:
      showkey("pub")
    if args.showpriv:
      showkey("pk")
    if args.genpsk:
      genpsk()

  except ConfigError as e:
    print(e)
    sys.exit(1)

