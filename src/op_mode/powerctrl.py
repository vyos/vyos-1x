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
from vyos.util import ask_yes_no


def parse_time(s):
  try:
    return datetime.strptime(s, "%H:%M").time()
  except ValueError:
    return None

def parse_date(s):
  for fmt in ["%d%m%Y", "%d/%m/%Y", "%d.%m.%Y", "%d:%m:%Y", "%Y-%m-%d"]:
    try:
      return datetime.strptime(s, fmt).date()
    except ValueError:
      continue
  # If nothing matched...
  return None

def get_shutdown_status():
  try:
    output = check_output(["/bin/systemctl", "status", "systemd-shutdownd.service"]).decode()
    return output
  except CalledProcessError:
    return None

def check_shutdown():
  output = get_shutdown_status()
  if output:
    r = re.findall(r'Status: \"(.*)\"\n', output)
    if r:
        # When available, that line is like
        # Status: "Shutting down at Thu 1970-01-01 00:00:00 UTC (poweroff)..."
        print(r[0])
    else:
        # Sometimes status string is not available immediately
        # after service startup
        print("Poweroff or reboot is scheduled")
  else:
    print("Poweroff or reboot is not scheduled")

def cancel_shutdown():
  output = get_shutdown_status()
  if output:
    try:
      timenow = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
      cmd = check_output(["/sbin/shutdown","-c","--no-wall"])
      message = "Scheduled reboot or poweroff has been cancelled %s" % timenow
      os.system("wall %s" % message)
    except CalledProcessError as e:
      sys.exit("Could not cancel a reboot or poweroff: %s" % e)
  else:
    print("Reboot or poweroff is not scheduled")

def execute_shutdown(time, reboot = True, ask=True):
  if not ask:
    action = "reboot" if reboot else "poweroff"
    if not ask_yes_no("Are you sure you want to %s this system?" % action):
      sys.exit(0)

  action = "-r" if reboot else "-P"

  if len(time) == 0:
    ### T870 legacy reboot job support
    chk_vyatta_based_reboots()
    ###

    cmd = check_output(["/sbin/shutdown",action,"now"],stderr=STDOUT)
    print(cmd.decode().split(",",1)[0])
    return
  elif len(time) == 1:
    # Assume the argument is just time
    ts = parse_time(time[0])
    if ts:
      cmd = check_output(["/sbin/shutdown", action, time[0]], stderr=STDOUT)
    else:
      sys.exit("Invalid time \"{0}\". The valid format is HH:MM".format(time[0]))
  elif len(time) == 2:
    # Assume it's date and time
    ts = parse_time(time[0])
    ds = parse_date(time[1])
    if ts and ds:
      t = datetime.combine(ds, ts)
      td = t - datetime.now()
      t2 = 1 + int(td.total_seconds())//60 # Get total minutes
      cmd = check_output(["/sbin/shutdown", action, str(t2)], stderr=STDOUT)
    else:
      if not ts:
        sys.exit("Invalid time \"{0}\". The valid format is HH:MM".format(time[0]))
      else:
        sys.exit("Invalid time \"{0}\". A valid format is YYYY-MM-DD [HH:MM]".format(time[1]))
  else:
    sys.exit("Could not decode date and time. Valids formats are HH:MM or YYYY-MM-DD HH:MM")
  check_shutdown()

def chk_vyatta_based_reboots():
  ### T870 commit-confirm is still using the vyatta code base, once gone, the code below can be removed
  ### legacy scheduled reboot s are using at and store the is as /var/run/<name>.job
  ### name is the node of scheduled the job, commit-confirm checks for that

  f = r'/var/run/confirm.job'
  if os.path.exists(f):
    jid = open(f).read().strip()
    if jid != 0:
      subprocess.call(['sudo', 'atrm', jid])
    os.remove(f)

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--yes", "-y",
            help="Do not ask for confirmation",
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

