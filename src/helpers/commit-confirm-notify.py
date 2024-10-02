#!/usr/bin/env python3
import os
import sys
import time
from argparse import ArgumentParser

# Minutes before reboot to trigger notification.
intervals = [1, 5, 15, 60]

parser = ArgumentParser()
parser.add_argument(
    'minutes', type=int, help='minutes before rollback to trigger notification'
)
parser.add_argument(
    '--reboot', action='store_true', help="use 'soft' rollback instead of reboot"
)


def notify(interval, reboot=False):
    s = '' if interval == 1 else 's'
    time.sleep((minutes - interval) * 60)
    if reboot:
        message = (
            '"[commit-confirm] System will reboot in '
            f'{interval} minute{s}\nto rollback the last commit.\n'
            'Confirm your changes to cancel the reboot."'
        )
        os.system('wall -n ' + message)
    else:
        message = (
            '"[commit-confirm] System will reload previous config in '
            f'{interval} minute{s}\nto rollback the last commit.\n'
            'Confirm your changes to cancel the reload."'
        )
        os.system('wall -n ' + message)


if __name__ == '__main__':
    # Must be run as root to call wall(1) without a banner.
    if os.getuid() != 0:
        print('This script requires superuser privileges.', file=sys.stderr)
        exit(1)

    args = parser.parse_args()

    minutes = args.minutes
    reboot = args.reboot

    # Drop the argument from the list so that the notification
    # doesn't kick in immediately.
    if minutes in intervals:
        intervals.remove(minutes)
    for interval in sorted(intervals, reverse=True):
        if minutes >= interval:
            notify(interval, reboot=reboot)
            minutes -= minutes - interval
    exit(0)
