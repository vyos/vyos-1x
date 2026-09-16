#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
from vyos.utils.process import cmdl
from vyos.utils.dict import dict_search_args
from vyos.utils.commit import commit_in_progress

# configure logging
logger = logging.getLogger(__name__)
logs_format = logging.Formatter('%(filename)s: %(message)s')
logs_handler_syslog = SysLogHandler('/dev/log')
logs_handler_syslog.setFormatter(logs_format)
logger.addHandler(logs_handler_syslog)
logger.setLevel(logging.DEBUG)

mdns_running_file = '/run/mdns_vrrp_active'
mdns_update_command = '/usr/libexec/vyos/conf_mode/service_mdns_repeater.py'


def lookup_transition_script(vrrp_config_dict, kind, name, state):
    """Look up the configured transition-script command for a VRRP
    notification.

    kind is 'group' or 'sync_group', matching the (mangled) top-level keys
    of vrrp_config_dict. name is used as a single dict key exactly as
    received from the keepalived notify line - never split, never
    reassembled into a delimited path.

    T9256 defect 1 was originally "the notify regex rejects names
    containing ':'". Widening the regex (see regex_notify in
    pipe_process()) only fixes matching the name out of the notify line.
    The two call sites here used to hand dict_search() an f-string path
    like f'group.{name}.transition_script.{state}' - dict_search() splits
    that path on '.', so any name containing a literal dot reproduces the
    exact same silent no-op one call downstream of the regex, and the
    same is true of any other character that collides with dict_search()'s
    own delimiter. dict_search_args() takes name as one positional
    argument and indexes by exact key with no parsing at all, so this is
    correct for any name the CLI's tag-node tokenizer accepts - not just
    the specific characters anyone happened to test.
    """
    return dict_search_args(
        vrrp_config_dict, kind, name, 'transition_script', state.lower()
    )


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

        # create queue for messages and events for synchronization
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
            cmdl(command.split())
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
        # The name is whatever the CLI accepted as a VRRP group/sync-group
        # name, framed by keepalived between literal double quotes - e.g.
        # INSTANCE "cluster:11" MASTER 100. The CLI does not restrict that
        # name to \w and -: colons are a common naming convention and are
        # accepted without complaint (T9256). Matching on the delimiter
        # itself, rather than trying to enumerate the accepted character
        # set, is what actually tracks what the CLI allows.
        regex_notify = re.compile(
            r'^(?P<type>\w+) "(?P<name>[^"]+)" (?P<state>\w+) (?P<priority>\d+)$',
            re.MULTILINE,
        )
        while self.stopme.is_set() is False:
            # wait for a new message event from pipe_wait
            self.message_event.wait()
            try:
                # clear message event flag
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
                                cmdl(mdns_update_command.split(), sudo=True)

                            tmp = lookup_transition_script(
                                self.vrrp_config_dict, 'group', n_name, n_state
                            )
                            if tmp is not None:
                                self._run_command(tmp)
                        # check and run commands for VRRP sync groups
                        elif n_type == 'GROUP':
                            if os.path.exists(mdns_running_file):
                                cmdl(mdns_update_command.split(), sudo=True)

                            tmp = lookup_transition_script(
                                self.vrrp_config_dict, 'sync_group', n_name, n_state
                            )
                            if tmp is not None:
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
        # keepalived may write more than we read in one call, and a read can
        # land in the middle of a line. Hold the incomplete trailing line here
        # and prepend it to the next read, so only whole lines are queued.
        buffer = ''
        while self.stopme.is_set() is False:
            # sleep a bit to not produce 100% CPU load
            time.sleep(0.250)
            try:
                # try to read a message from PIPE
                message = os.read(self.pipe_read, 500)
                if message:
                    buffer += message.decode()
                    # split PIPE content by lines and put them into queue,
                    # keeping the last (possibly incomplete) line for later
                    lines = buffer.split('\n')
                    buffer = lines.pop()
                    queued = False
                    for line in lines:
                        line = line.strip()
                        if line:
                            self.message_queue.put(line)
                            queued = True
                    # set new message flag to start processing
                    if queued:
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

def main():
    # __init__ parses argv and reads the live VRRP config, and the bottom
    # half below spawns real threads and opens a real FIFO - none of which
    # a unit test should trigger just by importing this module for its
    # pure functions (e.g. lookup_transition_script). Gating all of it
    # behind __name__ == '__main__' is what makes that possible, the same
    # way vyos-net-name-resolve.py / vyos-netlinkd already do it.
    global fifo, thread_wait_message, thread_process_message

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


if __name__ == '__main__':
    main()
