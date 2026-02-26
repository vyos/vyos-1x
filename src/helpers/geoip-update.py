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
from vyos.geoip import geoip_download_dbip
from vyos.geoip import geoip_download_maxmind
from vyos.geoip import db_initialise
from vyos.geoip import db_is_initialised
from vyos.geoip import db_import_dbip_ranges
from vyos.geoip import db_import_maxmind_ranges
from vyos.geoip import geoip_update

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = ConfigTreeQuery()

    return (
        conf.get_config_dict(['firewall', 'global-options', 'geoip'], key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True, with_defaults=True),
        conf.get_config_dict(['firewall'], key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True) if conf.exists(['firewall']) else None,
        conf.get_config_dict(['policy'], key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True) if conf.exists(['policy']) else None,
    )

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", help="Initialise", action="store_true")
    args = parser.parse_args()

    if args.init:
        db_initialise()
        db_import_dbip_ranges(delete_file=True)
        sys.exit(0)

    options, firewall, policy = get_config()

    if not db_is_initialised():
        db_initialise()

    if options['provider'] == 'db-ip':
        print('Dowloading latest DB-IP database...')
        if not geoip_download_dbip():
            print('Failed to download, aborting.')
            sys.exit(1)

        print('Extracting database...')
        if not db_import_dbip_ranges(delete_file=True):
            print('Failed to extract, aborting.')
            sys.exit(1)

    elif options['provider'] == 'maxmind':
        account_id = options['maxmind_account_id']
        license_key = options['maxmind_license_key']
        lite = 'maxmind_lite' in options

        print('Dowloading latest MaxMind database...')
        if not geoip_download_maxmind(account_id, license_key, lite):
            print('Failed to download, aborting.')
            sys.exit(1)

        print('Extracting database...')
        if not db_import_maxmind_ranges(delete_file=True):
            print('Failed to extract, aborting.')
            sys.exit(1)

    if not geoip_update(firewall=firewall, policy=policy):
        sys.exit(1)
