#!/usr/bin/env python3
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import re

from argparse import ArgumentParser
from datetime import datetime
from sys import exit
from time import time

from vyos.utils.io import ask_yes_no
from vyos.utils.process import call
from vyos.utils.process import run
from vyos.utils.process import STDOUT

systemd_sched_file = "/run/systemd/shutdown/scheduled"

def utc2local(datetime):
    now = time()
    offs = datetime.fromtimestamp(now) - datetime.utcfromtimestamp(now)
    return datetime + offs

def parse_time(s):
    try:
        if re.match(r'^\d{1,9999}$', s):
            if (int(s) > 59) and (int(s) < 1440):
                s = str(int(s)//60) + ":" + str(int(s)%60)
                return datetime.strptime(s, "%H:%M").time()
            if (int(s) >= 1440):
                return s.split()
            else:
                return datetime.strptime(s, "%M").time()
        else:
            return datetime.strptime(s, "%H:%M").time()
    except ValueError:
        return None


def parse_date(s):
    for fmt in ["%d%m%Y", "%d/%m/%Y", "%d.%m.%Y", "%d:%m:%Y", "%Y-%m-%d"]:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # If nothing matched...
    return None


def get_shutdown_status():
    if os.path.exists(systemd_sched_file):
        # Get scheduled from systemd file
        with open(systemd_sched_file, 'r') as f:
            data = f.read().rstrip('\n')
            r_data = {}
            for line in data.splitlines():
                tmp_split = line.split("=")
                if tmp_split[0] == "USEC":
                    # Convert USEC to  human readable format
                    r_data['DATETIME'] = datetime.utcfromtimestamp(
                        int(tmp_split[1])/1000000).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    r_data[tmp_split[0]] = tmp_split[1]
            return r_data
    return None


def check_shutdown():
    output = get_shutdown_status()
    if output and 'MODE' in output:
        dt = datetime.strptime(output['DATETIME'], '%Y-%m-%d %H:%M:%S')
        if output['MODE'] == 'reboot':
            print("Reboot is scheduled", utc2local(dt))
        elif output['MODE'] == 'poweroff':
            print("Poweroff is scheduled", utc2local(dt))
    else:
        print("Reboot or poweroff is not scheduled")


def cancel_shutdown():
    output = get_shutdown_status()
    if output and 'MODE' in output:
        timenow = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            run('/sbin/shutdown -c --no-wall')
        except OSError as e:
            exit(f'Could not cancel a reboot or poweroff: {e}')

        mode = output['MODE']
        message = f'Scheduled {mode} has been cancelled {timenow}'
        run(f'wall {message} > /dev/null 2>&1')
    else:
        print("Reboot or poweroff is not scheduled")

def check_unsaved_config():
    from vyos.config_mgmt import unsaved_commits
    from vyos.utils.boot import boot_configuration_success

    if unsaved_commits(allow_missing_config=True) and boot_configuration_success():
        print("Warning: there are unsaved configuration changes!")
        print("Run 'save' command if you do not want to lose those changes after reboot/shutdown.")
    else:
        pass

def execute_shutdown(time, reboot=True, ask=True):
    from vyos.utils.process import cmd

    check_unsaved_config()

    host = cmd("hostname --fqdn")

    action = "reboot" if reboot else "poweroff"
    if not ask:
        if not ask_yes_no(f"Are you sure you want to {action} this system ({host})?"):
            exit(0)
    action_cmd = "-r" if reboot else "-P"

    if len(time) == 0:
        # T870 legacy reboot job support
        chk_vyatta_based_reboots()
        ###

        out = cmd(f'/sbin/shutdown {action_cmd} now', stderr=STDOUT)
        print(out.split(",", 1)[0])
        return
    elif len(time) == 1:
        # Assume the argument is just time
        ts = parse_time(time[0])
        if ts:
            cmd(f'/sbin/shutdown {action_cmd} {time[0]}', stderr=STDOUT)
            # Inform all other logged in users about the reboot/shutdown
            wall_msg = f'System {action} is scheduled {time[0]}'
            cmd(f'/usr/bin/wall "{wall_msg}"')
        else:
            exit(f'Invalid time "{time[0]}". The valid format is HH:MM')
    elif len(time) == 2:
        # Assume it's date and time
        ts = parse_time(time[0])
        ds = parse_date(time[1])
        if ts and ds:
            t = datetime.combine(ds, ts)
            td = t - datetime.now()
            t2 = 1 + int(td.total_seconds())//60  # Get total minutes

            cmd(f'/sbin/shutdown {action_cmd} {t2}', stderr=STDOUT)
            # Inform all other logged in users about the reboot/shutdown
            wall_msg = f'System {action} is scheduled {time[1]} {time[0]}'
            cmd(f'/usr/bin/wall "{wall_msg}"')
        else:
            if not ts:
                exit(f'Invalid time "{time[0]}". Uses 24 Hour Clock format')
            else:
                exit(f'Invalid date "{time[1]}". A valid format is YYYY-MM-DD [HH:MM]')
    else:
        exit('Could not decode date and time. Valids formats are HH:MM or YYYY-MM-DD HH:MM')
    check_shutdown()


def chk_vyatta_based_reboots():
    # T870 commit-confirm is still using the vyatta code base, once gone, the code below can be removed
    # legacy scheduled reboot s are using at and store the is as /var/run/<name>.job
    # name is the node of scheduled the job, commit-confirm checks for that

    f = r'/var/run/confirm.job'
    if os.path.exists(f):
        jid = open(f).read().strip()
        if jid != 0:
            call(f'sudo atrm {jid}')
        os.remove(f)


def main():
    parser = ArgumentParser()
    parser.add_argument("--yes", "-y",
                        help="Do not ask for confirmation",
                        action="store_true",
                        dest="yes")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--reboot", "-r",
                        help="Reboot the system",
                        nargs="*",
                        metavar="HH:MM")

    action.add_argument("--reboot-in", "-i",
                        help="Reboot the system",
                        nargs="*",
                        metavar="Minutes")

    action.add_argument("--poweroff", "-p",
                        help="Poweroff the system",
                        nargs="*",
                        metavar="Minutes|HH:MM")

    action.add_argument("--cancel", "-c",
                        help="Cancel pending shutdown",
                        action="store_true")

    action.add_argument("--check",
                        help="Check pending shutdown",
                        action="store_true")
    args = parser.parse_args()

    try:
        if args.reboot is not None:
            for r in args.reboot:
                if ':' not in r and '/' not in r and '.' not in r:
                    print("Incorrect format! Use HH:MM")
                    exit(1)
            execute_shutdown(args.reboot, reboot=True, ask=args.yes)
        if args.reboot_in is not None:
            for i in args.reboot_in:
                if ':' in i:
                    print("Incorrect format! Use Minutes")
                    exit(1)
            execute_shutdown(args.reboot_in, reboot=True, ask=args.yes)
        if args.poweroff is not None:
            execute_shutdown(args.poweroff, reboot=False, ask=args.yes)
        if args.cancel:
            cancel_shutdown()
        if args.check:
            check_shutdown()
    except KeyboardInterrupt:
        exit("Interrupted")

if __name__ == "__main__":
    main()
