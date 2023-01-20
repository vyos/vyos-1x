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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys

from vyos import ConfigError
from vyos.config import Config
from vyos.config_mgmt import ConfigMgmt
from vyos.config_mgmt import commit_post_hook_dir, commit_hooks

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['system', 'config-management']
    if not conf.exists(base):
        return None

    mgmt = ConfigMgmt(config=conf)

    return mgmt

def verify(_mgmt):
    return

def generate(mgmt):
    if mgmt is None:
        return

    mgmt.initialize_revision()

def apply(mgmt):
    if mgmt is None:
        return

    locations = mgmt.locations
    archive_target = os.path.join(commit_post_hook_dir,
                               commit_hooks['commit_archive'])
    if locations:
        try:
            os.symlink('/usr/bin/config-mgmt', archive_target)
        except FileExistsError:
            pass
        except OSError as exc:
            raise ConfigError from exc
    else:
        try:
            os.unlink(archive_target)
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise ConfigError from exc

    revisions = mgmt.max_revisions
    revision_target = os.path.join(commit_post_hook_dir,
                               commit_hooks['commit_revision'])
    if revisions > 0:
        try:
            os.symlink('/usr/bin/config-mgmt', revision_target)
        except FileExistsError:
            pass
        except OSError as exc:
            raise ConfigError from exc
    else:
        try:
            os.unlink(revision_target)
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise ConfigError from exc

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
