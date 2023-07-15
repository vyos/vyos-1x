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

def chown(path, user, group):
    """ change file/directory owner """
    from pwd import getpwnam
    from grp import getgrnam

    if user is None or group is None:
        return False

    # path may also be an open file descriptor
    if not isinstance(path, int) and not os.path.exists(path):
        return False

    uid = getpwnam(user).pw_uid
    gid = getgrnam(group).gr_gid
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
    """ make file only read/writable by owner """
    from stat import S_IRUSR, S_IWUSR

    bitmask = S_IRUSR | S_IWUSR
    chmod(path, bitmask)

def chmod_750(path):
    """ make file/directory only executable to user and group """
    from stat import S_IRUSR, S_IWUSR, S_IXUSR, S_IRGRP, S_IXGRP

    bitmask = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP
    chmod(path, bitmask)

def chmod_755(path):
    """ make file executable by all """
    from stat import S_IRUSR, S_IWUSR, S_IXUSR, S_IRGRP, S_IXGRP, S_IROTH, S_IXOTH

    bitmask = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP | \
              S_IROTH | S_IXOTH
    chmod(path, bitmask)

def is_admin() -> bool:
    """Look if current user is in sudo group"""
    from getpass import getuser
    from grp import getgrnam
    current_user = getuser()
    (_, _, _, admin_group_members) = getgrnam('sudo')
    return current_user in admin_group_members

def get_cfg_group_id():
    from grp import getgrnam
    from vyos.defaults import cfg_group

    group_data = getgrnam(cfg_group)
    return group_data.gr_gid
