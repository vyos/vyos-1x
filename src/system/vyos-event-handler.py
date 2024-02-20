#!/usr/bin/env python3
#
# Copyright (C) 2022-2023 VyOS maintainers and contributors
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

import argparse
import json
import re
import select

from copy import deepcopy
from os import getpid, environ
from pathlib import Path
from signal import signal, SIGTERM, SIGINT
from sys import exit
from systemd import journal

from vyos.utils.dict import dict_search
from vyos.utils.process import run

# Identify this script
my_pid = getpid()
my_name = Path(__file__).stem

# handle termination signal
def handle_signal(signal_type, frame):
    if signal_type == SIGTERM:
        journal.send('Received SIGTERM signal, stopping normally',
                     SYSLOG_IDENTIFIER=my_name)
    if signal_type == SIGINT:
        journal.send('Received SIGINT signal, stopping normally',
                     SYSLOG_IDENTIFIER=my_name)
    exit(0)


# Class for analyzing and process messages
class Analyzer:
    # Initialize settings
    def __init__(self, config: dict) -> None:
        self.config = {}
        # Prepare compiled regex objects
        for event_id, event_config in config.items():
            script = dict_search('script.path', event_config)
            # Check for arguments
            if dict_search('script.arguments', event_config):
                script_arguments = dict_search('script.arguments', event_config)
                script = f'{script} {script_arguments}'
            # Prepare environment
            environment = deepcopy(environ)
            # Check for additional environment options
            if dict_search('script.environment', event_config):
                for env_variable, env_value in dict_search(
                        'script.environment', event_config).items():
                    environment[env_variable] = env_value.get('value')
            # Create final config dictionary
            pattern_raw = event_config['filter']['pattern']
            pattern_compiled = re.compile(
                rf'{event_config["filter"]["pattern"]}')
            pattern_config = {
                pattern_compiled: {
                    'pattern_raw':
                        pattern_raw,
                    'syslog_id':
                        dict_search('filter.syslog-identifier', event_config),
                    'pattern_script': {
                        'path': script,
                        'environment': environment
                    }
                }
            }
            self.config.update(pattern_config)

    # Execute script safely
    def script_run(self, pattern: str, script_path: str,
                   script_env: dict) -> None:
        try:
            run(script_path, env=script_env)
            journal.send(
                f'Pattern found: "{pattern}", script executed: "{script_path}"',
                SYSLOG_IDENTIFIER=my_name)
        except Exception as err:
            journal.send(
                f'Pattern found: "{pattern}", failed to execute script "{script_path}": {err}',
                SYSLOG_IDENTIFIER=my_name)

    # Analyze a message
    def process_message(self, message: dict) -> None:
        for pattern_compiled, pattern_config in self.config.items():
            # Check if syslog id is presented in config and matches
            syslog_id = pattern_config.get('syslog_id')
            if syslog_id and message['SYSLOG_IDENTIFIER'] != syslog_id:
                continue
            if pattern_compiled.fullmatch(message['MESSAGE']):
                # Add message to environment variables
                pattern_config['pattern_script']['environment'][
                    'message'] = message['MESSAGE']
                # Run script
                self.script_run(
                    pattern=pattern_config['pattern_raw'],
                    script_path=pattern_config['pattern_script']['path'],
                    script_env=pattern_config['pattern_script']['environment'])


if __name__ == '__main__':
    # Parse command arguments and get config
    parser = argparse.ArgumentParser()
    parser.add_argument('-c',
                        '--config',
                        action='store',
                        help='Path to even-handler configuration',
                        required=True,
                        type=Path)

    args = parser.parse_args()
    try:
        config_path = Path(args.config)
        config = json.loads(config_path.read_text())
        # Create an object for analazyng messages
        analyzer = Analyzer(config)
    except Exception as err:
        print(
            f'Configuration file "{config_path}" does not exist or malformed: {err}'
        )
        exit(1)

    # Prepare for proper exitting
    signal(SIGTERM, handle_signal)
    signal(SIGINT, handle_signal)

    # Set up journal connection
    data = journal.Reader()
    data.seek_tail()
    data.get_previous()
    p = select.poll()
    p.register(data, data.get_events())

    journal.send(f'Started with configuration: {config}',
                 SYSLOG_IDENTIFIER=my_name)

    while p.poll():
        if data.process() != journal.APPEND:
            continue
        for entry in data:
            message = entry['MESSAGE']
            pid = -1
            try:
                pid = entry['_PID']
            except Exception as ex:
                journal.send(f'Unable to extract PID from message entry: {entry}', SYSLOG_IDENTIFIER=my_name)
                continue            
            # Skip empty messages and messages from this process
            if message and pid != my_pid:
                try:
                    analyzer.process_message(entry)
                except Exception as err:
                    journal.send(f'Unable to process message: {err}',
                                 SYSLOG_IDENTIFIER=my_name)
