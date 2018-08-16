#!/usr/bin/env python3
import os
import sys
import argparse
from datetime import datetime, timedelta, time as type_time, date as type_date
from subprocess import check_output,CalledProcessError,STDOUT
import re

def yn(msg, default=False):
    default_msg = "[Y/n]" if default else "[y/N]"
    while True:
        sys.stdout.write("%s %s "  % (msg,default_msg))
        c = input().lower()
        if c == '':
            return default
        elif c in ("y", "ye","yes"):
            return True
        elif c in ("n", "no"):
            return False
        else:
            sys.stdout.write("Please respond with yes/y or no/n\n")


def valid_time(s):
    try:
        a = datetime.strptime(s, "%H:%M")
        return True
    except ValueError:
        return False


def check_shutdown():
    try:
        cmd = check_output(["/bin/systemctl","status","systemd-shutdownd.service"])
        #Shutodwn is scheduled
        r = re.findall(r'Status: \"(.*)\"\n', cmd.decode())[0]
        print(r)
    except CalledProcessError as e:
        #Shutdown is not scheduled
        print("Shutdown is not scheduled")

def cancel_shutdown():
    try:
        cmd = check_output(["/sbin/shutdown","-c"])
    except CalledProcessError as e:
        sys.exit("Error aborting shutdown: %s" % e)

def execute_shutdown(time, reboot = True, ask=True):
    if not ask:
        action = "reboot" if reboot else "poweroff"
        if not yn("Are you sure you want to %s this system?" % action):
            sys.exit(0)

    if not (time.isdigit() or valid_time(time) or time.lower() == "now"):
        sys.exit("minutes (45), valid time (12:34) or 'now' needs to be specified")

    action = "-r" if reboot else "-P"
    cmd = check_output(["/sbin/shutdown",action,time],stderr=STDOUT)

    print(cmd.decode().split(",",1)[0])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", "-y",
                        help="dont as for shutdown",
                        action="store_true",
                        dest="yes")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--reboot", "-r",
                        help="Reboot the system",
                        nargs="?",
                        metavar="Minutes|HH:MM")

    action.add_argument("--poweroff", "-p",
                        help="Poweroff the system",
                        nargs="?",
                        metavar="Minutes|HH:MM")

    action.add_argument("--cancel", "-c",
                        help="Cancel pending shutdown",
                        action="store_true")

    action.add_argument("--check",
                        help="Check pending chutdown",
                        action="store_true")
    args = parser.parse_args()

    try:
        if args.reboot:
            execute_shutdown(args.reboot, reboot=True, ask=args.yes)
        if args.poweroff:
            execute_shutdown(args.poweroff, reboot=False,ask=args.yes)
        if args.cancel:
            cancel_shutdown()
        if args.check:
            check_shutdown()
    except KeyboardInterrupt:
        sys.exit("Interrupted")


if __name__ == "__main__":
    main()
