# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

import os
import tempfile
import shutil

from vyos.utils.permission import chown

def makedir(path, user=None, group=None):
    if os.path.exists(path):
        return
    os.makedirs(path, mode=0o755)
    chown(path, user, group)

def file_is_persistent(path):
    import re
    location = r'^(/config|/opt/vyatta/etc/config)'
    absolute = os.path.abspath(os.path.dirname(path))
    return re.match(location,absolute)

def read_file(fname, defaultonfailure=None, sudo=False):
    """
    read the content of a file, stripping any end characters (space, newlines)
    should defaultonfailure be not None, it is returned on failure to read
    """
    try:
        # Some files can only be read by root - emulate sudo cat call
        if sudo:
            from vyos.utils.process import cmd
            data = cmd(['sudo', 'cat', fname])
        else:
            # If not sudo, just read the file
            with open(fname, 'r') as f:
                data = f.read()
        return data.strip()
    except Exception as e:
        if defaultonfailure is not None:
            return defaultonfailure
        raise e

def write_file(fname, data, defaultonfailure=None, user=None, group=None,
               mode=None, append=False, trailing_newline=False):
    """
    Write content of data to given fname, should defaultonfailure be not None,
    it is returned on failure to read.

    If directory of file is not present, it is auto-created.
    """
    dirname = os.path.dirname(fname)
    if dirname and not os.path.isdir(dirname):
        os.makedirs(dirname, mode=0o755, exist_ok=False)
        chown(dirname, user, group)

    try:
        """ Write a file to string """
        bytes = 0
        with open(fname, 'w' if not append else 'a') as f:
            bytes = f.write(data)
            if trailing_newline and not data.endswith('\n'):
                f.write('\n')
                bytes += 1
        chown(fname, user, group)
        chmod(fname, mode)
        return bytes
    except Exception as e:
        if defaultonfailure is not None:
            return defaultonfailure
        raise e

def read_json(fname, defaultonfailure=None):
    """
    read and json decode the content of a file
    should defaultonfailure be not None, it is returned on failure to read
    """
    import json
    try:
        with open(fname, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        if defaultonfailure is not None:
            return defaultonfailure
        raise e


def chmod(path, bitmask):
    # path may also be an open file descriptor
    if not isinstance(path, int) and not os.path.exists(path):
        return
    if bitmask is None:
        return
    os.chmod(path, bitmask)


def chmod_600(path):
    """ Make file only read/writable by owner """
    from stat import S_IRUSR, S_IWUSR

    bitmask = S_IRUSR | S_IWUSR
    chmod(path, bitmask)


def chmod_750(path):
    """ Make file/directory only executable to user and group """
    from stat import S_IRUSR, S_IWUSR, S_IXUSR, S_IRGRP, S_IXGRP

    bitmask = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP
    chmod(path, bitmask)


def chmod_755(path):
    """ Make file executable by all """
    from stat import S_IRUSR, S_IWUSR, S_IXUSR, S_IRGRP, S_IXGRP, S_IROTH, S_IXOTH

    bitmask = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP | \
              S_IROTH | S_IXOTH
    chmod(path, bitmask)

def chmod_2775(path):
    """ user/group permissions with set-group-id bit set """
    from stat import S_ISGID, S_IRWXU, S_IRWXG, S_IROTH, S_IXOTH

    bitmask = S_ISGID | S_IRWXU | S_IRWXG | S_IROTH | S_IXOTH
    chmod(path, bitmask)

def chmod_775(path):
    """ Make file executable by all """
    from stat import S_IRUSR, S_IWUSR, S_IXUSR, S_IRGRP, S_IWGRP, S_IXGRP, S_IROTH, S_IXOTH

    bitmask = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IWGRP | S_IXGRP | \
              S_IROTH | S_IXOTH
    chmod(path, bitmask)

def file_permissions(path):
    """ Return file permissions in string format, e.g '0755' """
    return oct(os.stat(path).st_mode)[4:]

def wait_for_inotify(file_path, pre_hook=None, event_type=None, timeout=None, sleep_interval=0.1):
    """ Waits for an inotify event to occur """
    if not os.path.dirname(file_path):
        raise ValueError(
          "File path {} does not have a directory part (required for inotify watching)".format(file_path))
    if not os.path.basename(file_path):
        raise ValueError(
          "File path {} does not have a file part, do not know what to watch for".format(file_path))

    from inotify.adapters import Inotify
    from time import time
    from time import sleep

    time_start = time()

    i = Inotify()
    i.add_watch(os.path.dirname(file_path))

    if pre_hook:
        pre_hook()

    for event in i.event_gen(yield_nones=True):
        if (timeout is not None) and ((time() - time_start) > timeout):
            # If the function didn't return until this point,
            # the file failed to have been written to and closed within the timeout
            raise OSError("Waiting for file {} to be written has failed".format(file_path))

        # Most such events don't take much time, so it's better to check right away
        # and sleep later.
        if event is not None:
            (_, type_names, path, filename) = event
            if filename == os.path.basename(file_path):
                if event_type in type_names:
                    return
        sleep(sleep_interval)

def wait_for_file_write_complete(file_path, pre_hook=None, timeout=None, sleep_interval=0.1):
    """ Waits for a process to close a file after opening it in write mode. """
    wait_for_inotify(file_path,
      event_type='IN_CLOSE_WRITE', pre_hook=pre_hook, timeout=timeout, sleep_interval=sleep_interval)


def copy_chown(source, target):
    # pylint: disable=import-outside-toplevel
    import shutil
    import stat

    shutil.copy2(source, target)
    st = os.stat(source)
    os.chown(target, st[stat.ST_UID], st[stat.ST_GID])


def write_file_sync(file_path, data: str, mode='w'):
    """Write file with explicit sync of file and directory"""
    # pylint: disable=consider-using-with
    file_dir = os.path.dirname(file_path)

    # write and sync file
    try:
        file = open(file_path, mode)
        file.write(data)
        file.flush()
        os.fsync(file.fileno())
        file.close()
    except OSError as e:
        try:
            file.close()
        except OSError:
            pass
        raise e

    # sync directory entry
    try:
        fd = os.open(file_dir, os.O_DIRECTORY | os.O_RDONLY)
        os.fsync(fd)
        os.close(fd)
    except OSError as e:
        try:
            os.close(fd)
        except OSError:
            pass
        raise e


def write_file_atomic(file_path, data: str, mode='w'):
    """Use os.rename for 'atomic' write.

    Note that this requires an euid/egid of that of the source file for the
    chown operation.

    Note that this calls write_file_sync, above.
    """
    # pylint: disable=consider-using-with,raise-missing-from
    file_dir = os.path.dirname(file_path)
    temp_file = tempfile.NamedTemporaryFile(delete=False, dir=file_dir).name

    def cleanup():
        if os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except OSError:
                pass

    if os.path.exists(file_path):
        try:
            copy_chown(file_path, temp_file)
        except OSError as e:
            cleanup()
            raise OSError(f'copy_chown {e}')

    try:
        write_file_sync(temp_file, data, mode=mode)
    except OSError as e:
        cleanup()
        raise OSError(f'write_file_sync {e}')

    try:
        os.rename(temp_file, file_path)
    except OSError as e:
        cleanup()
        raise OSError(f'rename {e}')

def copy_recursive(src: str, dst: str, overwrite: bool = False):
    """
    Recursively copy files from `src` to `dst`.

    :param src: Source directory
    :param dst: Destination directory
    :param overwrite: If True, overwrite existing files. If False, skip them.
    """

    if not os.path.exists(src):
        raise FileNotFoundError(f"Source path does not exist: {src}")

    os.makedirs(dst, exist_ok=True)  # Create destination directory if not exists

    for root, _, files in os.walk(src):
        # Find relative path to maintain directory structure
        rel_path = os.path.relpath(root, src)
        target_dir = os.path.join(dst, rel_path) if rel_path != "." else dst

        os.makedirs(target_dir, exist_ok=True)

        for file in files:
            src_file = os.path.join(root, file)
            dst_file = os.path.join(target_dir, file)

            if not os.path.exists(dst_file) or overwrite:
                shutil.copy2(src_file, dst_file)


def move_recursive(src: str, dst: str, overwrite=False):
    """
    Recursively move files from `src` to `dst` and removing the source.

    :param src: Source directory
    :param dst: Destination directory
    :param overwrite: If True, overwrite existing files. If False, skip them.
    """
    if not os.path.exists(src):
        raise FileNotFoundError(f"Source path does not exist: {src}")

    copy_recursive(src, dst, overwrite=overwrite)
    shutil.rmtree(src)
