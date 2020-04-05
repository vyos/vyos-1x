#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

import os
import time
import signal
import argparse
import threading
import re
import json
from pathlib import Path
from queue import Queue
import logging
from logging.handlers import SysLogHandler

from vyos.util import cmd

# configure logging
logger = logging.getLogger(__name__)
logs_format = logging.Formatter('%(filename)s: %(message)s')
logs_handler_syslog = SysLogHandler('/dev/log')
logs_handler_syslog.setFormatter(logs_format)
logger.addHandler(logs_handler_syslog)
logger.setLevel(logging.DEBUG)


# class for all operations
class KeepalivedFifo:
    # init - read command arguments
    def __init__(self):
        logger.info("Starting FIFO pipe for Keepalived")
        # define program arguments
        cmd_args_parser = argparse.ArgumentParser(description='Create FIFO pipe for keepalived and process notify events', add_help=False)
        cmd_args_parser.add_argument('PIPE', help='path to the FIFO pipe')
        # parse arguments
        cmd_args = cmd_args_parser.parse_args()
        self._config_load()
        self.pipe_path = cmd_args.PIPE

        # create queue for messages and events for syncronization
        self.message_queue = Queue(maxsize=100)
        self.stopme = threading.Event()
        self.message_event = threading.Event()

    # load configuration
    def _config_load(self):
        try:
            # read the dictionary file with configuration
            with open('/run/keepalived_config.dict', 'r') as dict_file:
                vrrp_config_dict = json.load(dict_file)
            self.vrrp_config = {'vrrp_groups': {}, 'sync_groups': {}}
            # save VRRP instances to the new dictionary
            for vrrp_group in vrrp_config_dict['vrrp_groups']:
                self.vrrp_config['vrrp_groups'][vrrp_group['name']] = {
                    'STOP': vrrp_group.get('stop_script'),
                    'FAULT': vrrp_group.get('fault_script'),
                    'BACKUP': vrrp_group.get('backup_script'),
                    'MASTER': vrrp_group.get('master_script')
                }
            # save VRRP sync groups to the new dictionary
            for sync_group in vrrp_config_dict['sync_groups']:
                self.vrrp_config['sync_groups'][sync_group['name']] = {
                    'STOP': sync_group.get('stop_script'),
                    'FAULT': sync_group.get('fault_script'),
                    'BACKUP': sync_group.get('backup_script'),
                    'MASTER': sync_group.get('master_script')
                }
            logger.debug("Loaded configuration: {}".format(self.vrrp_config))
        except Exception as err:
            logger.error("Unable to load configuration: {}".format(err))

    # run command
    def _run_command(self, command):
        logger.debug("Running the command: {}".format(command))
        try:
            cmd(command, universal_newlines=True)
        except OSError as err:
            logger.error(f'Unable to execute command "{command}": {err}')

    # create FIFO pipe
    def pipe_create(self):
        if Path(self.pipe_path).exists():
            logger.info("PIPE already exist: {}".format(self.pipe_path))
        else:
            os.mkfifo(self.pipe_path)

    # process message from pipe
    def pipe_process(self):
        logger.debug("Message processing start")
        regex_notify = re.compile(r'^(?P<type>\w+) "(?P<name>[\w-]+)" (?P<state>\w+) (?P<priority>\d+)$', re.MULTILINE)
        while self.stopme.is_set() is False:
            # wait for a new message event from pipe_wait
            self.message_event.wait()
            try:
                # clear mesage event flag
                self.message_event.clear()
                # get all messages from queue and try to process them
                while self.message_queue.empty() is not True:
                    message = self.message_queue.get()
                    logger.debug("Received message: {}".format(message))
                    notify_message = regex_notify.search(message)
                    # try to process a message if it looks valid
                    if notify_message:
                        n_type = notify_message.group('type')
                        n_name = notify_message.group('name')
                        n_state = notify_message.group('state')
                        logger.info("{} {} changed state to {}".format(n_type, n_name, n_state))
                        # check and run commands for VRRP instances
                        if n_type == 'INSTANCE':
                            if n_name in self.vrrp_config['vrrp_groups'] and n_state in self.vrrp_config['vrrp_groups'][n_name]:
                                n_script = self.vrrp_config['vrrp_groups'][n_name].get(n_state)
                                if n_script:
                                    self._run_command(n_script)
                        # check and run commands for VRRP sync groups
                        # currently, this is not available in VyOS CLI
                        if n_type == 'GROUP':
                            if n_name in self.vrrp_config['sync_groups'] and n_state in self.vrrp_config['sync_groups'][n_name]:
                                n_script = self.vrrp_config['sync_groups'][n_name].get(n_state)
                                if n_script:
                                    self._run_command(n_script)
                    # mark task in queue as done
                    self.message_queue.task_done()
            except Exception as err:
                logger.error("Error processing message: {}".format(err))
        logger.debug("Terminating messages processing thread")

    # wait for messages
    def pipe_wait(self):
        logger.debug("Message reading start")
        self.pipe_read = os.open(self.pipe_path, os.O_RDONLY | os.O_NONBLOCK)
        while self.stopme.is_set() is False:
            # sleep a bit to not produce 100% CPU load
            time.sleep(0.1)
            try:
                # try to read a message from PIPE
                message = os.read(self.pipe_read, 500)
                if message:
                    # split PIPE content by lines and put them into queue
                    for line in message.decode().strip().splitlines():
                        self.message_queue.put(line)
                    # set new message flag to start processing
                    self.message_event.set()
            except Exception as err:
                # ignore the "Resource temporarily unavailable" error
                if err.errno != 11:
                    logger.error("Error receiving message: {}".format(err))

        logger.debug("Closing FIFO pipe")
        os.close(self.pipe_read)


# handle SIGTERM signal to allow finish all messages processing
def sigterm_handle(signum, frame):
    logger.info("Ending processing: Received SIGTERM signal")
    fifo.stopme.set()
    thread_wait_message.join()
    fifo.message_event.set()
    thread_process_message.join()


signal.signal(signal.SIGTERM, sigterm_handle)

# init our class
fifo = KeepalivedFifo()
# try to create PIPE if it is not exist yet
# It looks like keepalived do it before the script will be running, but if we
# will decide to run this not from keepalived config, then we may get in
# trouble. So it is betteer to leave this here.
fifo.pipe_create()
# create and run dedicated threads for reading and processing messages
thread_wait_message = threading.Thread(target=fifo.pipe_wait)
thread_process_message = threading.Thread(target=fifo.pipe_process)
thread_wait_message.start()
thread_process_message.start()
