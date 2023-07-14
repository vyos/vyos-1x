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

from datetime import datetime
from pathlib import Path
from shutil import rmtree
from socket import gethostname
from sys import exit
from tarfile import open as tar_open
from vyos.utils.process import rc_cmd
import os

# define a list of commands that needs to be executed

CMD_LIST: list[str] = [
    "journalctl -b -n 500",
    "journalctl -b -k -n 500",
    "ip -s l",
    "cat /proc/interrupts",
    "cat /proc/softirqs",
    "top -b -d 1 -n 2 -1",
    "netstat -l",             
    "cat /proc/net/dev",
    "cat /proc/net/softnet_stat",
    "cat /proc/net/icmp",
    "cat /proc/net/udp",
    "cat /proc/net/tcp",
    "cat /proc/net/netstat",
    "sysctl net",
    "timeout 10 tcpdump -c 500 -eni any port not 22"
]

CMD_INTERFACES_LIST: list[str] = [
    "ethtool -i ",
    "ethtool -S ",
    "ethtool -g ",
    "ethtool -c ",
    "ethtool -a ",
    "ethtool -k ",
    "ethtool -i ",
    "ethtool --phy-statistics "
]

# get intefaces info
interfaces_list = os.popen('ls /sys/class/net/').read().split()

# modify CMD_INTERFACES_LIST for all interfaces
CMD_INTERFACES_LIST_MOD=[]
for command_interface in interfaces_list:
    for command_interfacev2 in CMD_INTERFACES_LIST:
        CMD_INTERFACES_LIST_MOD.append (f'{command_interfacev2}{command_interface}')

# execute a command and save the output to a file

def save_stdout(command: str, file: Path) -> None:
    rc, stdout = rc_cmd(command)
    body: str = f'''### {command} ###
Command: {command}
Exit code: {rc}
Stdout:
{stdout}

'''
    with file.open(mode='a') as f:
        f.write(body)

# get local host name
hostname: str = gethostname()
# get current time
time_now: str = datetime.now().isoformat(timespec='seconds')

# define a temporary directory for logs and collected data
tmp_dir: Path = Path(f'/tmp/drops-debug_{time_now}')
# set file paths
drops_file: Path = Path(f'{tmp_dir}/drops.txt')
interfaces_file: Path = Path(f'{tmp_dir}/interfaces.txt')
archive_file: str = f'/tmp/packet-drops-debug_{time_now}.tar.bz2'

# create files
tmp_dir.mkdir()
drops_file.touch()
interfaces_file.touch()

try:
    # execute all commands
    for command in CMD_LIST:
        save_stdout(command, drops_file)
    for command_interface in CMD_INTERFACES_LIST_MOD:
        save_stdout(command_interface, interfaces_file)

    # create an archive
    with tar_open(name=archive_file, mode='x:bz2') as tar_file:
        tar_file.add(tmp_dir)

    # inform user about success
    print(f'Debug file is generated and located in {archive_file}')
except Exception as err:
    print(f'Error during generating a debug file: {err}')
finally:
    # cleanup
    rmtree(tmp_dir)
    exit()
