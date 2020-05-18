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
import logging
from logging.handlers import SysLogHandler
from pathlib import Path
import psutil

from vyos.command import call

# some default values
watchfrr = '/usr/lib/frr/watchfrr.sh'
vtysh = '/usr/bin/vtysh'
frrconfig_tmp = '/tmp/frr_restart'

# configure logging
logger = logging.getLogger(__name__)
logs_handler = SysLogHandler('/dev/log')
logs_handler.setFormatter(logging.Formatter('%(filename)s: %(message)s'))
logger.addHandler(logs_handler)
logger.setLevel(logging.INFO)

# check if it is safe to restart FRR
def _check_safety():
    try:
        # print warning
        answer = input("WARNING: This is a potentially unsafe function! You may lose the connection to the router or active configuration after running this command. Use it at your own risk! Continue? [y/N]: ")
        if not answer.lower() == "y":
            logger.error("User aborted command")
            return False

        # check if another restart process already running
        if len([process for process in psutil.process_iter(attrs=['pid', 'name', 'cmdline']) if 'python' in process.info['name'] and 'restart_frr.py' in process.info['cmdline'][1]]) > 1:
            logger.error("Another restart_frr.py already running")
            answer = input("Another restart_frr.py process is already running. It is unsafe to continue. Do you want to process anyway? [y/N]: ")
            if not answer.lower() == "y":
                return False

        # check if watchfrr.sh is running
        for process in psutil.process_iter(attrs=['pid', 'name', 'cmdline']):
            if 'bash' in process.info['name'] and watchfrr in process.info['cmdline']:
                logger.error("Another {} already running".format(watchfrr))
                answer = input("Another {} process is already running. It is unsafe to continue. Do you want to process anyway? [y/N]: ".format(watchfrr))
                if not answer.lower() == "y":
                    return False

        # check if vtysh is running
        for process in psutil.process_iter(attrs=['pid', 'name', 'cmdline']):
            if 'vtysh' in process.info['name']:
                logger.error("The vtysh is running by another task")
                answer = input("The vtysh is running by another task. It is unsafe to continue. Do you want to process anyway? [y/N]: ")
                if not answer.lower() == "y":
                    return False

        # check if temporary directory exists
        if Path(frrconfig_tmp).exists():
            logger.error("The temporary directory \"{}\" already exists".format(frrconfig_tmp))
            answer = input("The temporary directory \"{}\" already exists. It is unsafe to continue. Do you want to process anyway? [y/N]: ".format(frrconfig_tmp))
            if not answer.lower() == "y":
                return False
    except:
        logger.error("Something goes wrong in _check_safety()")
        return False

    # return True if all check was passed or user confirmed to ignore they results
    return True

# write active config to file
def _write_config():
    # create temporary directory
    Path(frrconfig_tmp).mkdir(parents=False, exist_ok=True)
    # save frr.conf to it
    command = "{} -n -w --config_dir {} 2> /dev/null".format(vtysh, frrconfig_tmp)
    return_code = call(command)
    if not return_code == 0:
        logger.error("Failed to save active config: \"{}\" returned exit code: {}".format(command, return_code))
        return False
    logger.info("Active config saved to {}".format(frrconfig_tmp))
    return True

# clear and remove temporary directory
def _cleanup():
    tmpdir = Path(frrconfig_tmp)
    try:
        if tmpdir.exists():
            for file in tmpdir.iterdir():
                file.unlink()
            tmpdir.rmdir()
    except:
        logger.error("Failed to remove temporary directory {}".format(frrconfig_tmp))
        print("Failed to remove temporary directory {}".format(frrconfig_tmp))

# check if daemon is running
def _daemon_check(daemon):
    command = "{} print_status {}".format(watchfrr, daemon)
    return_code = call(command)
    if not return_code == 0:
        logger.error("Daemon \"{}\" is not running".format(daemon))
        return False

    # return True if all checks were passed
    return True

# restart daemon
def _daemon_restart(daemon):
    command = "{} restart {}".format(watchfrr, daemon)
    return_code = call(command)
    if not return_code == 0:
        logger.error("Failed to restart daemon \"{}\"".format(daemon))
        return False

    # return True if restarted successfully
    logger.info("Daemon \"{}\" restarted".format(daemon))
    return True

# reload old config
def _reload_config(daemon):
    if daemon != '':
        command = "{} -n -b --config_dir {} -d {} 2> /dev/null".format(vtysh, frrconfig_tmp, daemon)
    else:
        command = "{} -n -b --config_dir {} 2> /dev/null".format(vtysh, frrconfig_tmp)

    return_code = call(command)
    if not return_code == 0:
        logger.error("Failed to reinstall configuration")
        return False

    # return True if restarted successfully
    logger.info("Configuration reinstalled successfully")
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
    # check if it is safe to restart FRR
    if not _check_safety():
        print("\nOne of the safety checks was failed or user aborted command. Exiting.")
        sys.exit(1)

    if not _write_config():
        print("Failed to save active config")
        _cleanup()
        sys.exit(1)

    # a little trick to make further commands more clear
    if not cmd_args.daemon:
        cmd_args.daemon = ['']

    # check all daemons if they are running
    if cmd_args.daemon != ['']:
        if not _check_args_daemon(cmd_args.daemon):
            print("Warning: some of listed daemons are not running")

    # run command to restart daemon
    for daemon in cmd_args.daemon:
        if not _daemon_restart(daemon):
            print("Failed to restart daemon: {}".format(daemon))
            _cleanup()
            sys.exit(1)
        # reinstall old configuration
        _reload_config(daemon)

    # cleanup after all actions
    _cleanup()

sys.exit(0)
