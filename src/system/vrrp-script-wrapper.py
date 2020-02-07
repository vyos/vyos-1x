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

import os
import sys
import subprocess
import argparse
import syslog

import vyos.util
import vyos.keepalived


parser = argparse.ArgumentParser()
parser.add_argument("-t", "--state", type=str, help="VRRP state")
parser.add_argument("-g", "--group", type=str, help="VRRP group")
parser.add_argument("-i", "--interface", type=str, help="Network interface")
parser.add_argument("-f", "--force", type=str, help="enable|disable force mode")
parser.add_argument("script", nargs='+')

syslog.openlog('vyos-vrrp-wrapper')

args = parser.parse_args()
if not args.script or not args.state or not args.group \
  or not args.interface:
    parser.print_usage()
    sys.exit(1)

# Fixup: the reason we take multiple "script" arguments is that people may want
# to pass arguments to the script
args.script = " ".join(args.script)

# Get the old state if it exists and compare it to the current state received
# in command line options to avoid executing scripts if no real transition occured.
# This is necessary because keepalived does not keep persistent state data even between
# config reloads and will cheerfully execute everything whether it's required or not.
if args.force != "enable":
    old_state = vyos.keepalived.get_old_state(args.group)
else:
    old_state = None

exitcode = 0
if (old_state is None) or (old_state != args.state):
    # Run the script and save the new state

    # Change the process GID to the config owners group to avoid screwing up
    # running config permissions
    os.setgid(vyos.util.get_cfg_group_id())

    syslog.syslog(syslog.LOG_NOTICE, 'Running transition script {0} for VRRP group {1}'.format(args.script, args.group))
    try:
       ret = subprocess.call("%s %s %s %s" % ( args.script, args.state, args.interface, args.group), shell=True)
       if ret != 0:
           syslog.syslog(syslog.LOG_ERR, "Transition script {0} failed, exit status: {1}".format(args.script, ret))
           exitcode = ret
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, "Failed to execute transition script {0}: {1}".format(args.script, e))
        exitcode = 1

    if exitcode == 0:
        syslog.syslog(syslog.LOG_NOTICE, "Transition script {0} executed successfully".format(args.script))

    vyos.keepalived.save_state(args.group, args.state)
else:
    syslog.syslog(syslog.LOG_NOTICE, "State of the group {0} has not changed, not running transition script".format(args.group))

syslog.closelog()
sys.exit(exitcode)
