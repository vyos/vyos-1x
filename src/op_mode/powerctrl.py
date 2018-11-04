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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import argparse
import subprocess
import re

from datetime import datetime, timedelta, time as type_time, date as type_date
from subprocess import check_output, CalledProcessError, STDOUT

def yn(msg, default=False):
  default_msg = "[Y/n]" if default else "[y/N]"
  while True:
    sys.stdout.write("%s %s "  % (msg,default_msg))
    c = input().lower()
    if c == '':
      return default
    elif c in ("y", "ye","yes"):
      return True
    elif c in ("n", "no"):
      return False
    else:
      sys.stdout.write("Please respond with yes/y or no/n\n")


def valid_time(s):
  try:
    return datetime.strptime(s, "%H:%M").time()
  except ValueError:
    return None


def valid_date(s):
  try:
    return datetime.strptime(s, "%d%m%Y").date()
  except ValueError:
    try:
      return datetime.strptime(s, "%d/%m/%Y").date()
    except ValueError:
      try:
        return datetime.strptime(s, "%d.%m.%Y").date()
      except ValueError:
        try:
          return datetime.strptime(s, "%d:%m:%Y").date()
        except ValueError:
          return None


def check_shutdown():
  try:
    cmd = check_output(["/bin/systemctl","status","systemd-shutdownd.service"])
    #Shutodwn is scheduled
    r = re.findall(r'Status: \"(.*)\"\n', cmd.decode())[0]
    print(r)
  except CalledProcessError as e:
    #Shutdown is not scheduled
    print("Shutdown is not scheduled")

def cancel_shutdown():
  try:
    cmd = check_output(["/sbin/shutdown","-c"])
  except CalledProcessError as e:
    sys.exit("Error aborting shutdown: %s" % e)

def execute_shutdown(time, reboot = True, ask=True):
  if not ask:
    action = "reboot" if reboot else "poweroff"
    if not yn("Are you sure you want to %s this system?" % action):
      sys.exit(0)

  action = "-r" if reboot else "-P"

  if len(time) == 0:
    ### T870 legacy reboot job support
    chk_vyatta_based_reboots()
    ###

    cmd = check_output(["/sbin/shutdown",action,"now"],stderr=STDOUT)
    print(cmd.decode().split(",",1)[0])
    return

  # Try to extract date from the first argument
  if len(time) == 1:
    time = time[0].split(" ",1)

  if len(time) == 1:
    ts = valid_time(time[0])
    if time[0].isdigit() or valid_time(time[0]):
      cmd = check_output(["/sbin/shutdown",action,time[0]],stderr=STDOUT)
    else:
      sys.exit("Timestamp needs to be in format of 12:34")

  elif len(time) == 2:
    ts = valid_time(time[0])
    ds = valid_date(time[1])
    if ts and ds:
      t = datetime.combine(ds, ts)
      td = t - datetime.now()
      t2 = 1 + int(td.total_seconds())//60 # Get total minutes
      cmd = check_output(["/sbin/shutdown",action,str(t2)],stderr=STDOUT)
    else:
      sys.exit("Timestamp needs to be in format of 12:34\nDatestamp in the format of DD.MM.YY")
  else:
    sys.exit("Could not decode time and date")

  print(cmd.decode().split(",",1)[0])

def chk_vyatta_based_reboots():
  ### T870 commit-confirm is still using the vyatta code base, once gone, the code below can be removed
  ### legacy scheduled reboot s are using at and store the is as /var/run/<name>.job
  ### name is the node of scheduled the job, commit-confirm checks for that

  f = r'/var/run/confirm.job'
  if os .path.exists(f):
    jid = open(f).read().strip()
    if jid != 0:
      subprocess.call(['sudo', 'atrm', jid])
    os.remove(f)

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--yes", "-y",
            help="dont as for shutdown",
            action="store_true",
            dest="yes")
  action = parser.add_mutually_exclusive_group(required=True)
  action.add_argument("--reboot", "-r",
            help="Reboot the system",
            nargs="*",
            metavar="Minutes|HH:MM")

  action.add_argument("--poweroff", "-p",
            help="Poweroff the system",
            nargs="*",
            metavar="Minutes|HH:MM")

  action.add_argument("--cancel", "-c",
            help="Cancel pending shutdown",
            action="store_true")

  action.add_argument("--check",
            help="Check pending chutdown",
            action="store_true")
  args = parser.parse_args()

  try:
    if  args.reboot is not None:
      execute_shutdown(args.reboot, reboot=True, ask=args.yes)
    if args.poweroff is not None:
      execute_shutdown(args.poweroff, reboot=False,ask=args.yes)
    if args.cancel:
      cancel_shutdown()
    if args.check:
      check_shutdown()
  except KeyboardInterrupt:
    sys.exit("Interrupted")


if __name__ == "__main__":
  main()
