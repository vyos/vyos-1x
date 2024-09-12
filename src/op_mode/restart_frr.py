#!/usr/bin/env python3
#
# Copyright (C) 2019-2023 VyOS maintainers and contributors
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

import os
import argparse
import logging
import psutil

from logging.handlers import SysLogHandler
from shutil import rmtree

from vyos.base import Warning
from vyos.utils.io import ask_yes_no
from vyos.utils.file import makedir
from vyos.utils.process import call
from vyos.utils.process import process_named_running

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
        if not ask_yes_no('WARNING: This is a potentially unsafe function!\n' \
                          'You may lose the connection to the router or active configuration after\n' \
                          'running this command. Use it at your own risk!\n\n'
                          'Continue?'):
            return False

        # check if another restart process already running
        if len([process for process in psutil.process_iter(attrs=['pid', 'name', 'cmdline']) if 'python' in process.info['name'] and 'restart_frr.py' in process.info['cmdline'][1]]) > 1:
            message = 'Another restart_frr.py process is already running!'
            logger.error(message)
            if not ask_yes_no(f'\n{message} It is unsafe to continue.\n\n' \
                              'Do you want to process anyway?'):
                return False

        # check if watchfrr.sh is running
        tmp = os.path.basename(watchfrr)
        if process_named_running(tmp):
            message = f'Another {tmp} process is already running.'
            logger.error(message)
            if not ask_yes_no(f'{message} It is unsafe to continue.\n\n' \
                              'Do you want to process anyway?'):
                return False

        # check if vtysh is running
        if process_named_running('vtysh'):
            message = 'vtysh process is executed by another task.'
            logger.error(message)
            if not ask_yes_no(f'{message} It is unsafe to continue.\n\n' \
                              'Do you want to process anyway?'):
                return False

        # check if temporary directory exists
        if os.path.exists(frrconfig_tmp):
            message = f'Temporary directory "{frrconfig_tmp}" already exists!'
            logger.error(message)
            if not ask_yes_no(f'{message} It is unsafe to continue.\n\n' \
                              'Do you want to process anyway?'):
                return False

    except:
        logger.error("Something goes wrong in _check_safety()")
        return False

    # return True if all check was passed or user confirmed to ignore they results
    return True

# write active config to file
def _write_config():
    # create temporary directory
    makedir(frrconfig_tmp)
    # save frr.conf to it
    command = f'{vtysh} -n -w --config_dir {frrconfig_tmp} 2> /dev/null'
    return_code = call(command)
    if return_code != 0:
        logger.error(f'Failed to save active config: "{command}" returned exit code: {return_code}')
        return False
    logger.info(f'Active config saved to {frrconfig_tmp}')
    return True

# clear and remove temporary directory
def _cleanup():
    if os.path.isdir(frrconfig_tmp):
        rmtree(frrconfig_tmp)

# restart daemon
def _daemon_restart(daemon):
    command = f'{watchfrr} restart {daemon}'
    return_code = call(command)
    if not return_code == 0:
        logger.error(f'Failed to restart daemon "{daemon}"!')
        return False

    # return True if restarted successfully
    logger.info(f'Daemon "{daemon}" restarted!')
    return True

# reload old config
def _reload_config(daemon):
    if daemon != '':
        command = f'{vtysh} -n -b --config_dir {frrconfig_tmp} -d {daemon} 2> /dev/null'
    else:
        command = f'{vtysh} -n -b --config_dir {frrconfig_tmp} 2> /dev/null'

    return_code = call(command)
    if not return_code == 0:
        logger.error('Failed to re-install configuration!')
        return False

    # return True if restarted successfully
    logger.info('Configuration re-installed successfully!')
    return True

# define program arguments
cmd_args_parser = argparse.ArgumentParser(description='restart frr daemons')
cmd_args_parser.add_argument('--action', choices=['restart'], required=True, help='action to frr daemons')
cmd_args_parser.add_argument('--daemon', choices=['zebra', 'staticd', 'bgpd', 'eigrpd', 'ospfd', 'ospf6d', 'ripd', 'ripngd', 'isisd', 'pimd', 'pim6d', 'ldpd', 'babeld', 'bfdd', 'fabricd'], required=False,  nargs='*', help='select single or multiple daemons')
# parse arguments
cmd_args = cmd_args_parser.parse_args()

# main logic
# restart daemon
if cmd_args.action == 'restart':
    # check if it is safe to restart FRR
    if not _check_safety():
        print("\nOne of the safety checks was failed or user aborted command. Exiting.")
        exit(1)

    if not _write_config():
        print("Failed to save active config")
        _cleanup()
        exit(1)

    # a little trick to make further commands more clear
    if not cmd_args.daemon:
        cmd_args.daemon = ['']

    # check all daemons if they are running
    if cmd_args.daemon != ['']:
        for daemon in cmd_args.daemon:
            if not process_named_running(daemon):
                Warning('some of listed daemons are not running!')

    # run command to restart daemon
    for daemon in cmd_args.daemon:
        if not _daemon_restart(daemon):
            print('Failed to restart daemon: {daemon}')
            _cleanup()
            exit(1)
        # reinstall old configuration
        _reload_config(daemon)

    # cleanup after all actions
    _cleanup()

exit(0)
