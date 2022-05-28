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

from sys import argv
from os import getpid
from systemd import journal
from vyos.util import call


parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", action="store", help="Path to even-handler configuration", required=True)

args = parser.parse_args()
config = args.config
data = journal.Reader()
data.seek_tail()
data.get_previous()
p = select.poll()
p.register(data, data.get_events())
my_pid = getpid()

with open(config, 'r') as f:
    config = json.load(f)


if __name__ == '__main__':
    while p.poll():
        if data.process() != journal.APPEND:
            continue
        for entry in data:
            message = entry['MESSAGE']
            for name, event_config in config.items():
                pattern = re.compile(rf'{event_config["pattern"]}')
                script = event_config['script']
                if message != "" and entry['_PID'] != my_pid and pattern.match(message):
                    call(script)
                    journal.send(f'Pattern found: {event_config["pattern"]}, script executed: {script}')
