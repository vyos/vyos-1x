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

# define a list of commands that needs to be executed
CMD_LIST: list[str] = [
    'swanctl -L',
    'swanctl -l',
    'swanctl -P',
    'ip x sa show',
    'ip x policy show',
    'ip tunnel show',
    'ip address',
    'ip rule show',
    'ip route | head -100',
    'ip route show table 220'
]
JOURNALCTL_CMD: str = 'journalctl --no-hostname --boot --unit strongswan.service'

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
tmp_dir: Path = Path(f'/tmp/ipsec_debug_{time_now}')
# set file paths
ipsec_status_file: Path = Path(f'{tmp_dir}/ipsec_status.txt')
journalctl_charon_file: Path = Path(f'{tmp_dir}/journalctl_charon.txt')
archive_file: str = f'/tmp/ipsec_debug_{time_now}.tar.bz2'

# create files
tmp_dir.mkdir()
ipsec_status_file.touch()
journalctl_charon_file.touch()

try:
    # execute all commands
    for command in CMD_LIST:
        save_stdout(command, ipsec_status_file)
    save_stdout(JOURNALCTL_CMD, journalctl_charon_file)

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
