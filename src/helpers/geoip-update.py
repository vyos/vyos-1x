#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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

import argparse
import sys

from vyos.configquery import ConfigTreeQuery
from vyos.firewall import geoip_update

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = ConfigTreeQuery()
    base = ['firewall']

    if not conf.exists(base):
        return None

    return conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", help="Force update", action="store_true")
    args = parser.parse_args()

    firewall = get_config()

    if not geoip_update(firewall, force=args.force):
        sys.exit(1)
