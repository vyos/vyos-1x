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

from sys import exit
from shutil import rmtree

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.template import render
from vyos.util import call
from vyos.util import cmd
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()
from pprint import pprint

gwlbtun_dir = '/run/aws'
gwlbtun_config = f'{gwlbtun_dir}/gwlbtun.conf'
systemd_service = 'aws-gwlbtun.service'
systemd_override = '/run/systemd/system/aws-gwlbtun.service.d/10-override.conf'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'aws', 'glb']
    if not conf.exists(base):
        return None

    glb = conf.get_config_dict(base, key_mangling=('-', '_'),
                                      get_first_key=True,
                                      no_tag_node_value_mangle=True)

    from pprint import pprint
    pprint(glb)
    return glb


def verify(glb):
    # bail out early - looks like removal from running config
    if not glb:
        return None


def generate(glb):
    if not glb:
        if os.path.isfile(gwlbtun_config):
            os.unlink(gwlbtun_config)

        return None

    if not os.path.isdir(gwlbtun_dir):
        os.mkdir(gwlbtun_dir)

    render(gwlbtun_config, 'aws/gwlbtun.conf.j2', glb)
    render(systemd_override, 'aws/override_aws_gwlbtun.conf.j2', glb)


def apply(glb):
    if not glb:
        call(f'systemctl stop {systemd_service}')
    else:
        call(f'systemctl restart {systemd_service}')
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
