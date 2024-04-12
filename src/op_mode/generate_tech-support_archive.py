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
import os
import argparse
import glob
from datetime import datetime
from pathlib import Path
from shutil import rmtree

from socket import gethostname
from sys import exit
from tarfile import open as tar_open
from vyos.utils.process import rc_cmd
from vyos.remote import upload

def op(cmd: str) -> str:
    """Returns a command with the VyOS operational mode wrapper."""
    return f'/opt/vyatta/bin/vyatta-op-cmd-wrapper {cmd}'

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
def __rotate_logs(path: str, log_pattern:str):
    files_list = glob.glob(f'{path}/{log_pattern}')
    if len(files_list) > 5:
        oldest_file = min(files_list, key=os.path.getctime)
        os.remove(oldest_file)


def __generate_archived_files(location_path: str) -> None:
    """
    Generate arhives of main directories
    :param location_path: path to temporary directory
    :type location_path: str
    """
    # Dictionary arhive_name:directory_to_arhive
    archive_dict = {
        'etc': '/etc',
        'home': '/home',
        'var-log': '/var/log',
        'root': '/root',
        'tmp': '/tmp',
        'core-dump': '/var/core',
        'config': '/opt/vyatta/etc/config'
    }
    # Dictionary arhive_name:excluding pattern
    archive_excludes = {
        # Old location of archives
        'config': 'tech-support-archive',
        # New locations of arhives
        'tmp': 'tech-support-archive'
    }
    for archive_name, path in archive_dict.items():
        archive_file: str = f'{location_path}/{archive_name}.tar.gz'
        with tar_open(name=archive_file, mode='x:gz') as tar_file:
            if archive_name in archive_excludes:
                tar_file.add(path, filter=lambda x: None if str(archive_excludes[archive_name]) in str(x.name) else x)
            else:
                tar_file.add(path)


def __generate_main_archive_file(archive_file: str, tmp_dir_path: str) -> None:
    """
    Generate main arhive file
    :param archive_file: name of arhive file
    :type archive_file: str
    :param tmp_dir_path: path to arhive memeber
    :type tmp_dir_path: str
    """
    with tar_open(name=archive_file, mode='x:gz') as tar_file:
        tar_file.add(tmp_dir_path, arcname=os.path.basename(tmp_dir_path))


if __name__ == '__main__':
    defualt_tmp_dir = '/tmp'
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs='?', default=defualt_tmp_dir)
    args = parser.parse_args()
    location_path = args.path[:-1] if args.path[-1] == '/' else args.path

    hostname: str = gethostname()
    time_now: str = datetime.now().isoformat(timespec='seconds').replace(":", "-")

    remote = False
    tmp_path = ''
    tmp_dir_path = ''
    if 'ftp://' in args.path or 'scp://' in args.path:
        remote = True
        tmp_path = defualt_tmp_dir
    else:
        tmp_path = location_path
    archive_pattern = f'_tech-support-archive_'
    archive_file_name = f'{hostname}{archive_pattern}{time_now}.tar.gz'

    # Log rotation in tmp directory
    if tmp_path == defualt_tmp_dir:
        __rotate_logs(tmp_path, f'*{archive_pattern}*')

    # Temporary directory creation
    tmp_dir_path = f'{tmp_path}/drops-debug_{time_now}'
    tmp_dir: Path = Path(tmp_dir_path)
    tmp_dir.mkdir(parents=True)

    report_file: Path = Path(f'{tmp_dir_path}/show_tech-support_report.txt')
    report_file.touch()
    try:

        save_stdout(op('show tech-support report'), report_file)
        # Generate included archives
        __generate_archived_files(tmp_dir_path)

        # Generate main archive
        __generate_main_archive_file(f'{tmp_path}/{archive_file_name}', tmp_dir_path)
        # Delete temporary directory
        rmtree(tmp_dir)
        # Upload to remote site if it is scpecified
        if remote:
            upload(f'{tmp_path}/{archive_file_name}', args.path)
        print(f'Debug file is generated and located in {location_path}/{archive_file_name}')
    except Exception as err:
        print(f'Error during generating a debug file: {err}')
        # cleanup
        if tmp_dir.exists():
            rmtree(tmp_dir)
    finally:
        # cleanup
        exit()
