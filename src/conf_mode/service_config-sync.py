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
import json
from pathlib import Path

from vyos.config import Config
from vyos import ConfigError
from vyos import airbag

airbag.enable()


service_conf = Path(f'/run/config_sync_conf.conf')
post_commit_dir = '/run/scripts/commit/post-hooks.d'
post_commit_file_src = '/usr/libexec/vyos/vyos_config_sync.py'
post_commit_file = f'{post_commit_dir}/vyos_config_sync'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['service', 'config-sync']
    if not conf.exists(base):
        return None
    config = conf.get_config_dict(base, get_first_key=True,
                                  with_recursive_defaults=True)

    return config


def verify(config):
    # bail out early - looks like removal from running config
    if not config:
        return None

    if 'mode' not in config:
        raise ConfigError(f'config-sync mode is mandatory!')

    for option in ['secondary', 'section']:
        if option not in config:
            raise ConfigError(f"config-sync '{option}' is not configured!")

    if 'address' not in config['secondary']:
        raise ConfigError(f'secondary address is mandatory!')
    if 'key' not in config['secondary']:
        raise ConfigError(f'secondary key is mandatory!')


def generate(config):
    if not config:

        if os.path.exists(post_commit_file):
            os.unlink(post_commit_file)

        if service_conf.exists():
            service_conf.unlink()

        return None

    # Write configuration file
    conf_json = json.dumps(config, indent=4)
    service_conf.write_text(conf_json)

    # Create post commit dir
    if not os.path.isdir(post_commit_dir):
        os.makedirs(post_commit_dir)

    # Symlink from helpers to post-commit
    if not os.path.exists(post_commit_file):
        os.symlink(post_commit_file_src, post_commit_file)

    return None


def apply(config):
    return None


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
