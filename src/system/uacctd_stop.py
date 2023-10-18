#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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

# Control pmacct daemons in a tricky way.
# Pmacct has signal processing in a main loop, together with packet
# processing. Because of this, while it is waiting for packets, it cannot
# handle the control signal. We need to start the systemctl command and then
# send some packets to pmacct to wake it up

from argparse import ArgumentParser
from socket import socket, AF_INET, SOCK_DGRAM
from sys import exit
from time import sleep

from psutil import Process


def stop_process(pid: int, timeout: int) -> None:
    """Send a signal to uacctd
    and then send packets to special address predefined in a firewall
    to unlock main loop in uacctd and finish the process properly

    Args:
        pid (int): uacctd PID
        timeout (int): seconds to wait for a process end
    """
    # find a process
    uacctd = Process(pid)
    uacctd.terminate()

    # create a socket
    trigger = socket(AF_INET, SOCK_DGRAM)

    first_cycle: bool = True
    while uacctd.is_running() and timeout:
        print('sending a packet to uacctd...')
        trigger.sendto(b'WAKEUP', ('127.0.254.0', 1))
        # do not sleep during first attempt
        if not first_cycle:
            sleep(1)
            timeout -= 1
        first_cycle = False


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('process_id',
                        type=int,
                        help='PID file of uacctd core process')
    parser.add_argument('timeout',
                        type=int,
                        help='time to wait for process end')
    args = parser.parse_args()
    stop_process(args.process_id, args.timeout)
    exit()
