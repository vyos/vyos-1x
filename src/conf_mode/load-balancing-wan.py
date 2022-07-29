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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from sys import exit

from vyos.config import Config
from vyos.configdict import node_changed
from vyos.util import call
from vyos import ConfigError
from pprint import pprint
from vyos import airbag
airbag.enable()


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['load-balancing', 'wan']
    lb = conf.get_config_dict(base, get_first_key=True,
                                       no_tag_node_value_mangle=True)

    pprint(lb)
    return lb

def verify(lb):
    return None


def generate(lb):
    if not lb:
        return None

    return None


def apply(lb):

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
