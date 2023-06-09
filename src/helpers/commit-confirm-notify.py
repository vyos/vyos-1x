#!/usr/bin/env python3
import os
import sys
import time

# Minutes before reboot to trigger notification.
intervals = [1, 5, 15, 60]

def notify(interval):
    s = "" if interval == 1 else "s"
    time.sleep((minutes - interval) * 60)
    message = ('"[commit-confirm] System is going to reboot in '
               f'{interval} minute{s} to rollback the last commit.\n'
               'Confirm your changes to cancel the reboot."')
    os.system("wall -n " + message)

if __name__ == "__main__":
    # Must be run as root to call wall(1) without a banner.
    if len(sys.argv) != 2 or os.getuid() != 0:
        print('This script requires superuser privileges.', file=sys.stderr)
        exit(1)
    minutes = int(sys.argv[1])
    # Drop the argument from the list so that the notification
    # doesn't kick in immediately.
    if minutes in intervals:
        intervals.remove(minutes)
    for interval in sorted(intervals, reverse=True):
        if minutes >= interval:
            notify(interval)
            minutes -= (minutes - interval)
    exit(0)
