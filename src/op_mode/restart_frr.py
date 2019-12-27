#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
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

import sys
import argparse
import subprocess
import logging
from logging.handlers import SysLogHandler

# some default values
watchfrr = '/usr/lib/frr/watchfrr.sh'
vtysh = '/usr/bin/vtysh'

# configure logging
logger = logging.getLogger(__name__)
logs_handler = SysLogHandler('/dev/log')
logs_handler.setFormatter(logging.Formatter('%(filename)s: %(message)s'))
logger.addHandler(logs_handler)
logger.setLevel(logging.INFO)

# write active config to file
def _write_config():
    command = "sudo {} -n -c write ".format(vtysh)
    return_code = subprocess.call(command, shell=True)
    if not return_code == 0:
        logger.error("Failed to save active config: \"{}\" returned exit code: {}".format(command, return_code))
        print("Failed to save active config: \"{}\" returned exit code: {}".format(command, return_code))
        sys.exit(1)
    logger.info("Active config saved to /etc/frr/frr.conf")

# check if daemon is running
def _daemon_check(daemon):
    command = "sudo {} print_status {}".format(watchfrr, daemon)
    return_code = subprocess.call(command, shell=True)
    if not return_code == 0:
        logger.error("Daemon \"{}\" is not running".format(daemon))
        return False

    # return True if all checks were passed
    return True

# restart daemon
def _daemon_restart(daemon):
    command = "sudo {} restart {}".format(watchfrr, daemon)
    return_code = subprocess.call(command, shell=True)
    if not return_code == 0:
        logger.error("Failed to restart daemon \"{}\"".format(daemon))
        return False

    # return True if restarted sucessfully
    logger.info("Daemon \"{}\" restarted".format(daemon))
    return True

# check all daemons if they are running
def _check_args_daemon(daemons):
    for daemon in daemons:
        if not _daemon_check(daemon):
            return False
    return True

# define program arguments
cmd_args_parser = argparse.ArgumentParser(description='restart frr daemons')
cmd_args_parser.add_argument('--action', choices=['restart'], required=True, help='action to frr daemons')
cmd_args_parser.add_argument('--daemon', choices=['bfdd', 'bgpd', 'ospfd', 'ospf6d', 'ripd', 'ripngd', 'staticd', 'zebra'], required=False,  nargs='*', help='select single or multiple daemons')
# parse arguments
cmd_args = cmd_args_parser.parse_args()


# main logic
# restart daemon
if cmd_args.action == 'restart':
    _write_config()
    if cmd_args.daemon:
        # check all daemons if they are running
        if not _check_args_daemon(cmd_args.daemon):
            print("Warning: some of listed daemons are not running")

        # run command to restart daemon
        for daemon in cmd_args.daemon:
            if not _daemon_restart(daemon):
                print("Failed to restart daemon: {}".format(daemon))
                sys.exit(1)
    else:
        # run command to restart FRR
        if not _daemon_restart(''):
            print("Failed to restart FRRouting")
            sys.exit(1)

sys.exit(0)
