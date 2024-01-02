# Copyright 2023 VyOS maintainers and contributors <maintainers@vyos.io>
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

def read_file(fname, defaultonfailure=None):
    """
    read the content of a file, stripping any end characters (space, newlines)
    should defaultonfailure be not None, it is returned on failure to read
    """
    try:
        """ Read a file to string """
        with open(fname, 'r') as f:
            data = f.read().strip()
        return data
    except Exception as e:
        if defaultonfailure is not None:
            return defaultonfailure
        raise e

def write_file(fname, data, defaultonfailure=None, user=None, group=None, mode=None, append=False):
    """
    Write content of data to given fname, should defaultonfailure be not None,
    it is returned on failure to read.

    If directory of file is not present, it is auto-created.
    """
    dirname = os.path.dirname(fname)
    if not os.path.isdir(dirname):
        os.makedirs(dirname, mode=0o755, exist_ok=False)
        chown(dirname, user, group)

    try:
        """ Write a file to string """
        bytes = 0
        with open(fname, 'w' if not append else 'a') as f:
            bytes = f.write(data)
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

def chown(path, user=None, group=None, recursive=False):
    """ change file/directory owner """
    from pwd import getpwnam
    from grp import getgrnam

    if user is None and group is None:
        return False

    # path may also be an open file descriptor
    if not isinstance(path, int) and not os.path.exists(path):
        return False

    # keep current value if not specified otherwise
    uid = -1
    gid = -1

    if user:
        uid = getpwnam(user).pw_uid
    if group:
        gid = getgrnam(group).gr_gid

    if recursive:
        for dirpath, dirnames, filenames in os.walk(path):
            os.chown(dirpath, uid, gid)
            for filename in filenames:
                os.chown(os.path.join(dirpath, filename), uid, gid)
    else:
        os.chown(path, uid, gid)
    return True


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

def makedir(path, user=None, group=None):
    if os.path.exists(path):
        return
    os.makedirs(path, mode=0o755)
    chown(path, user, group)

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
