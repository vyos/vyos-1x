#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

from vyos.defaults import directories
from vyos.utils.process import call
from vyos.utils.process import cmd
from vyos.utils.file import get_name_from_path
from vyos.remote import upload


# Example: bdbdd9a4807f_tech-support-archive_2026-02-02T13-53-18
ARCHIVE_PATTERN = '_tech-support-archive_'
# Example: drops-debug_2026-02-02T13-53-18
ARCHIVE_TMP_DIR_PATTERN = 'drops-debug_'
DEFAULT_TMP_DIR = '/tmp'
EXCLUDED_ARCHIVE_EXT = ('.iso', '.gz', '.tar', '.zip')


def __rotate_logs(path: str, log_pattern:str):
    files_list = glob.glob(f'{path}/{log_pattern}')
    if len(files_list) > 5:
        oldest_file = min(files_list, key=os.path.getctime)
        os.remove(oldest_file)


def __save_show_report_files(reports_dir: Path):
    """
    Save result of execution `show tech-support report` command
    :param reports_dir: path to the result directory
    :type reports_dir: pathlib.Path
    """

    vyos_op_scripts_dir = directories['op_mode']
    script_path = f'{vyos_op_scripts_dir}/show_techsupport_report.py'
    arguments = [
        '--launched-from-generate-archive',
        '--outdir',
        str(reports_dir),
    ]
    output = cmd([script_path] + arguments)

    if output.strip():
        print(output)


def __generate_archived_files(location_path: str) -> None:
    """
    Generate archives of main directories
    :param location_path: path to temporary directory
    :type location_path: str
    """

    # sync/flush journald before archiving /var/log/journal
    cmd(['journalctl', '--sync'])
    cmd(['journalctl', '--flush'])

    def __tar_filter(tarinfo):
        # path inside tar, because we set arcname=... below
        name = tarinfo.name
        basename = os.path.basename(name)

        # /var/log: exclude /var/log/messages and /var/log/messages.*
        if name.startswith('var/log/messages'):
            if basename == 'messages' or basename.startswith('messages.'):
                return None

        # /tmp, /home: exclude previous tech-support archives and temporary archive directories
        if name.startswith(('tmp/', 'home/')):
            if ARCHIVE_PATTERN in name or basename.startswith(ARCHIVE_TMP_DIR_PATTERN):
                return None

        # /home, /opt/vyatta/etc/config, /tmp: exclude general archives
        if name.startswith(('home/', 'opt/vyatta/etc/config/', 'tmp/')):
            if basename.lower().endswith(EXCLUDED_ARCHIVE_EXT):
                return None

        return tarinfo

    # Dictionary arhive_name:directory_to_arhive
    archive_dict = {
        'etc': '/etc',
        'home': '/home',
        'var-log': '/var/log',
        'root': '/root',
        'tmp': '/tmp',
        'core-dump': '/var/core',
        'config': '/opt/vyatta/etc/config',
        'run': '/run',
    }

    for archive_name, path in archive_dict.items():
        if not os.path.exists(path):
            continue

        arcname = str(path).lstrip('/')  # e.g. /etc -> 'etc'

        archive_file = f'{location_path}/{archive_name}.tar.gz'
        with tar_open(name=archive_file, mode='x:gz') as tar_file:
            try:
                tar_file.add(path, arcname=arcname, filter=__tar_filter)
            except (PermissionError, OSError) as e:
                print(f'Unable to read `{path}` to archive files:', e)
                continue  # skip paths we can't read


def __generate_main_archive_file(archive_file: str, tmp_dir_path: str) -> None:
    """
    Generate main archive file
    :param archive_file: name of archive file
    :type archive_file: str
    :param tmp_dir_path: path to archive member
    :type tmp_dir_path: str
    """

    arcname = get_name_from_path(archive_file)
    with tar_open(name=archive_file, mode='x:gz') as tar_file:
        tar_file.add(tmp_dir_path, arcname=arcname)

def __generate_topology_snapshots(output_dir: Path) -> None:
    """
    Generates physical and logical topology PNG files using `lstopo`

    :param output_dir: directory where topology PNGs will be stored
    """

    physical_topo = output_dir / 'topology.png'
    logical_topo = output_dir / 'topology-logical.png'

    # Capture physical topology
    call(['lstopo', '--output-format', 'png', str(physical_topo)])

    # Capture logical topology
    call(['lstopo', '--logical', '--output-format', 'png', str(logical_topo)])


def __resolve_main_archive_path(input_path: str, default_archive_name: str) -> Path:
    """
    Normalize path for saving a .tar.gz file based on rules:

    Rules:
      - file               -> file.tar.gz
      - file.tar           -> file.tar.gz
      - file.tgz           -> file.tgz
      - dir/               -> dir/{default_archive_name}
      - ../dir/file.tar.gz -> (unchanged)
      - file.zip           -> file.tar.gz

    :param input_path: user's provided path to the archive
    :param default_archive_name: name of archive if user didn't provide it
    """

    path = Path(input_path)

    # Case 1: default temporary directory -> extend by default name of file
    if input_path == DEFAULT_TMP_DIR:
        return path / default_archive_name

    # Case 2: already .tar.gz -> return unchanged
    if path.name.endswith(('.tar.gz', '.tgz')):
        return path

    # Case 3: already .tar -> .tar.gz
    if path.name.endswith('.tar'):
        return path.with_suffix('.tar.gz')

    # Case 4: directory (explicit trailing slash OR existing directory)
    if input_path.endswith(('/', '\\')) or path.is_dir():
        dir_path = path
        return dir_path / default_archive_name

    # Default behavior for any other extension
    return path.with_suffix('.tar.gz')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', nargs='?', default=DEFAULT_TMP_DIR)
    args = parser.parse_args()

    hostname: str = gethostname()
    time_now: str = datetime.now().isoformat(timespec='seconds').replace(':', '-')
    default_archive_inner_dir = f'{hostname}{ARCHIVE_PATTERN}{time_now}'
    default_archive_name = f'{default_archive_inner_dir}.tar.gz'

    is_remote = args.path.startswith(('ftp://', 'scp://'))
    if is_remote:
        base_tmp_path = DEFAULT_TMP_DIR
        archive_dest_path = Path(f'{base_tmp_path}/{default_archive_name}')
    else:
        # Define destination path to the main archive file based on a rules
        archive_dest_path = __resolve_main_archive_path(args.path, default_archive_name)
        base_tmp_path = str(archive_dest_path.parent)
        default_archive_name = archive_dest_path.name
        default_archive_inner_dir = get_name_from_path(archive_dest_path.name)

    # Log rotation in tmp directory
    if base_tmp_path == DEFAULT_TMP_DIR:
        __rotate_logs(base_tmp_path, f'*{ARCHIVE_PATTERN}*')

    # Temporary directory creation
    tmp_dir: Path = Path(f'{base_tmp_path}/{ARCHIVE_TMP_DIR_PATTERN}{time_now}')
    tmp_dir.mkdir(parents=True)

    # Directory which contains list of 'tech-support' reports
    reports_dir: Path = Path(f'{tmp_dir}/show_tech-support_report')

    # Call the topology snapshot function here
    __generate_topology_snapshots(tmp_dir)

    try:
        # Generate files using `show tech-support report` command
        __save_show_report_files(reports_dir)

        # Generate included archives
        __generate_archived_files(tmp_dir)

        # Generate main archive
        __generate_main_archive_file(archive_dest_path, tmp_dir)

        # Upload to remote site if it is scpecified
        if is_remote:
            upload_uri = args.path
            upload(str(archive_dest_path), upload_uri)
    except Exception as err:
        print(f'Error during generating a debug file: {err}')
    else:
        print(f'Debug file is generated and located in {archive_dest_path}')
    finally:
        # Delete temporary directory
        if tmp_dir.exists():
            rmtree(tmp_dir, ignore_errors=True)
        exit()
