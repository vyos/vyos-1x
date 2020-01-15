# Copyright 2018 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import re
import os
import signal
import json

import vyos.util


pid_file = '/var/run/keepalived.pid'
state_file = '/tmp/keepalived.data'
stats_file = '/tmp/keepalived.stats'
json_file = '/tmp/keepalived.json'

def vrrp_running():
    if not os.path.exists(vyos.keepalived.pid_file) \
      or not vyos.util.process_running(vyos.keepalived.pid_file):
        return False
    else:
        return True

def keepalived_running():
    return vyos.util.process_running(pid_file)

## Clear VRRP data after showing
def remove_vrrp_data(data_file):
    if data_file == "json" and os.path.exists(json_file):
        os.remove(json_file)
    elif data_file == "stats" and os.path.exists(stats_file):
        os.remove(stats_file)
    elif data_file == "state" and os.path.exists(state_file):
        os.remove(state_file)

def force_state_data_dump():
    pid = vyos.util.read_file(pid_file)
    os.kill(int(pid), signal.SIGUSR1)

def force_stats_dump():
    pid = vyos.util.read_file(pid_file)
    os.kill(int(pid), signal.SIGUSR2)

def force_json_dump():
    pid = vyos.util.read_file(pid_file)
    os.kill(int(pid), signal.SIGRTMIN+2)

def get_json_data():
    with open(json_file, 'r') as f:
        j = json.load(f)
    return j

def get_statistics():
    return vyos.util.read_file(stats_file)

def get_state_data():
    return vyos.util.read_file(state_file)

def decode_state(code):
    state = None
    if code == 0:
        state = "INIT"
    elif code == 1:
        state = "BACKUP"
    elif code == 2:
        state = "MASTER"
    elif code == 3:
        state = "FAULT"
    else:
        state = "UNKNOWN"

    return state

## These functions are for the old, and hopefully obsolete plaintext
## (non machine-readable) data format introduced by Vyatta back in the days
## They are kept here just in case, if JSON output option turns out or becomes
## insufficient.

def read_state_data():
    with open(state_file, 'r') as f:
        lines = f.readlines()
    return lines

def parse_keepalived_data(data_lines):
    vrrp_groups = {}

    # Scratch variable
    group_name = None

    # Sadly there is no explicit end marker in that format, so we have
    # only two states, one before the first VRRP instance is encountered
    # and one after an instance/"group" was encountered
    # We'll set group_name once the first group is encountered,
    # and assume we are inside a group if it's set afterwards
    #
    # It may not be necessary since the keywords found inside groups and before
    # the VRRP Topology section seem to have no intersection,
    # but better safe than sorry.

    for line in data_lines:
        if re.match(r'^\s*VRRP Instance', line, re.IGNORECASE):
            # Example: "VRRP Instance = Foo"
            name = re.match(r'^\s*VRRP Instance\s+=\s+(.*)$', line, re.IGNORECASE).groups()[0].strip()
            group_name = name
            vrrp_groups[name] = {}
        elif re.match(r'^\s*State', line, re.IGNORECASE) and group_name:
            # Example: "  State = MASTER"
            group_state = re.match(r'^\s*State\s+=\s+(.*)$', line, re.IGNORECASE).groups()[0].strip()
            vrrp_groups[group_name]["state"] = group_state
        elif re.match(r'^\s*Last transition', line, re.IGNORECASE) and group_name:
            # Example: "  Last transition = 1532043820 (Thu Jul 19 23:43:40 2018)"
            trans_time = re.match(r'^\s*Last transition\s+=\s+(\d+)\s', line, re.IGNORECASE).groups()[0]
            vrrp_groups[group_name]["last_transition"] = trans_time
        elif re.match(r'^\s*Interface', line, re.IGNORECASE) and group_name:
            # Example: "  Interface = eth0.30"
            interface = re.match(r'\s*Interface\s+=\s+(.*)$', line, re.IGNORECASE).groups()[0].strip()
            vrrp_groups[group_name]["interface"] = interface
        elif re.match(r'^\s*Virtual Router ID', line, re.IGNORECASE) and group_name:
            # Example: "  Virtual Router ID = 14"
            vrid = re.match(r'^\s*Virtual Router ID\s+=\s+(.*)$', line, re.IGNORECASE).groups()[0].strip()
            vrrp_groups[group_name]["vrid"] = vrid
        elif re.match(r'^\s*------< Interfaces', line, re.IGNORECASE):
            # Interfaces section appears to always be present,
            # and there's nothing of interest for us below that section,
            # so we use it as an end of input marker
            break

    return vrrp_groups
