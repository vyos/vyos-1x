#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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
import select
import re
import json
from os import getpid
from pathlib import Path
from signal import signal, SIGTERM, SIGINT
from systemd import journal
from sys import exit
from vyos.util import call

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


# Execute script safely
def script_run(pattern: str, script_path: str) -> None:
    try:
        call(script_path)
        journal.send(
            f'Pattern found: "{pattern}", script executed: "{script_path}"',
            SYSLOG_IDENTIFIER=my_name)
    except Exception as err:
        journal.send(
            f'Pattern found: "{pattern}", failed to execute script "{script_path}": {err}',
            SYSLOG_IDENTIFIER=my_name)


# iterate trough regexp items
def analyze_message(message: str, regex_patterns: dict) -> None:
    for pattern_compiled, pattern_config in regex_patterns.items():
        if pattern_compiled.match(message):
            script_run(pattern_config['pattern_raw'],
                       pattern_config['pattern_script'])


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

    # Prepare compiled regex objects
    patterns = {}
    for name, event_config in config.items():
        pattern_raw = f'{event_config["pattern"]}'
        pattern_compiled = re.compile(rf'{event_config["pattern"]}')
        pattern_config = {
            pattern_compiled: {
                'pattern_raw': pattern_raw,
                'pattern_script': event_config['script']
            }
        }
        patterns.update(pattern_config)

    journal.send(f'Started with configuration: {config}',
                 SYSLOG_IDENTIFIER=my_name)

    while p.poll():
        if data.process() != journal.APPEND:
            continue
        for entry in data:
            message = entry['MESSAGE']
            pid = entry['_PID']
            # Skip empty messages and messages from this process
            if message and pid != my_pid:
                analyze_message(message, patterns)
