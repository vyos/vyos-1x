#!/usr/bin/env python3
#
# Copyright (C) 2020-2024 VyOS maintainers and contributors
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
import time
import signal
import argparse
import threading
import re
import logging

from queue import Queue
from logging.handlers import SysLogHandler

from vyos.configquery import ConfigTreeQuery
from vyos.utils.process import cmd
from vyos.utils.dict import dict_search
from vyos.utils.commit import commit_in_progress

# configure logging
logger = logging.getLogger(__name__)
logs_format = logging.Formatter('%(filename)s: %(message)s')
logs_handler_syslog = SysLogHandler('/dev/log')
logs_handler_syslog.setFormatter(logs_format)
logger.addHandler(logs_handler_syslog)
logger.setLevel(logging.DEBUG)

mdns_running_file = '/run/mdns_vrrp_active'
mdns_update_command = 'sudo /usr/libexec/vyos/conf_mode/service_mdns_repeater.py'

# class for all operations
class KeepalivedFifo:
    # init - read command arguments
    def __init__(self):
        logger.info('Starting FIFO pipe for Keepalived')
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
        # For VRRP configuration to be read, the commit must be finished
        count = 1
        while commit_in_progress():
            if ( count <= 20 ):
                logger.debug(f'Attempt to load keepalived configuration aborted due to a commit in progress (attempt {count}/20)')
            else:
                logger.error(f'Forced keepalived configuration loading despite a commit in progress ({count} wait time expired, not waiting further)')
                break
            count += 1
            time.sleep(1)

        try:
            base = ['high-availability', 'vrrp']
            conf = ConfigTreeQuery()
            if not conf.exists(base):
                raise ValueError()

            # Read VRRP configuration directly from CLI
            self.vrrp_config_dict = conf.get_config_dict(base,
                                     key_mangling=('-', '_'), get_first_key=True,
                                     no_tag_node_value_mangle=True)

            logger.debug(f'Loaded configuration: {self.vrrp_config_dict}')
        except Exception as err:
            logger.error(f'Unable to load configuration: {err}')

    # run command
    def _run_command(self, command):
        logger.debug(f'Running the command: {command}')
        try:
            cmd(command)
        except OSError as err:
            logger.error(f'Unable to execute command "{command}": {err}')

    # create FIFO pipe
    def pipe_create(self):
        if os.path.exists(self.pipe_path):
            logger.info(f'PIPE already exist: {self.pipe_path}')
        else:
            os.mkfifo(self.pipe_path)

    # process message from pipe
    def pipe_process(self):
        logger.debug('Message processing start')
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
                    logger.debug(f'Received message: {message}')
                    notify_message = regex_notify.search(message)
                    # try to process a message if it looks valid
                    if notify_message:
                        n_type = notify_message.group('type')
                        n_name = notify_message.group('name')
                        n_state = notify_message.group('state')
                        logger.info(f'{n_type} {n_name} changed state to {n_state}')
                        # check and run commands for VRRP instances
                        if n_type == 'INSTANCE':
                            if os.path.exists(mdns_running_file):
                                cmd(mdns_update_command)

                            tmp = dict_search(f'group.{n_name}.transition_script.{n_state.lower()}', self.vrrp_config_dict)
                            if tmp != None:
                                self._run_command(tmp)
                        # check and run commands for VRRP sync groups
                        elif n_type == 'GROUP':
                            if os.path.exists(mdns_running_file):
                                cmd(mdns_update_command)

                            tmp = dict_search(f'sync_group.{n_name}.transition_script.{n_state.lower()}', self.vrrp_config_dict)
                            if tmp != None:
                                self._run_command(tmp)
                    # mark task in queue as done
                    self.message_queue.task_done()
            except Exception as err:
                logger.error(f'Error processing message: {err}')
        logger.debug('Terminating messages processing thread')

    # wait for messages
    def pipe_wait(self):
        logger.debug('Message reading start')
        self.pipe_read = os.open(self.pipe_path, os.O_RDONLY | os.O_NONBLOCK)
        while self.stopme.is_set() is False:
            # sleep a bit to not produce 100% CPU load
            time.sleep(0.250)
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
                    logger.error(f'Error receiving message: {err}')

        logger.debug('Closing FIFO pipe')
        os.close(self.pipe_read)

# handle SIGTERM signal to allow finish all messages processing
def sigterm_handle(signum, frame):
    logger.info('Ending processing: Received SIGTERM signal')
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
