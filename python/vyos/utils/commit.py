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

def commit_in_progress():
    """ Not to be used in normal op mode scripts! """

    # The CStore backend locks the config by opening a file
    # The file is not removed after commit, so just checking
    # if it exists is insufficient, we need to know if it's open by anyone

    # There are two ways to check if any other process keeps a file open.
    # The first one is to try opening it and see if the OS objects.
    # That's faster but prone to race conditions and can be intrusive.
    # The other one is to actually check if any process keeps it open.
    # It's non-intrusive but needs root permissions, else you can't check
    # processes of other users.
    #
    # Since this will be used in scripts that modify the config outside of the CLI
    # framework, those knowingly have root permissions.
    # For everything else, we add a safeguard.
    from psutil import process_iter
    from psutil import NoSuchProcess
    from getpass import getuser
    from vyos.defaults import commit_lock

    if getuser() != 'root':
        raise OSError('This functions needs to be run as root to return correct results!')

    for proc in process_iter():
        try:
            files = proc.open_files()
            if files:
                for f in files:
                    if f.path == commit_lock:
                        return True
        except NoSuchProcess as err:
            # Process died before we could examine it
            pass
    # Default case
    return False


def wait_for_commit_lock():
    """ Not to be used in normal op mode scripts! """
    from time import sleep
    # Very synchronous approach to multiprocessing
    while commit_in_progress():
        sleep(1)
