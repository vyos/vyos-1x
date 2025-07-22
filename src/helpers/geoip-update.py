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

    return (
        conf.get_config_dict(['firewall'], key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True) if conf.exists(['firewall']) else None,
        conf.get_config_dict(['policy'], key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True) if conf.exists(['policy']) else None,
    )

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", help="Force update", action="store_true")
    args = parser.parse_args()

    firewall, policy = get_config()
    if not geoip_update(firewall=firewall, policy=policy, force=args.force):
        sys.exit(1)
