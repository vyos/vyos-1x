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

import argparse
import sys

from pathlib import Path
from systemd import journal

from vyos.configquery import ConfigTreeQuery
from vyos.util import rc_cmd


my_name = Path(__file__).stem


def find_interface_by_eni_id(eni_id_to_find: str, config: dict):
    interfaces = config.get('interfaces', {})
    for interface, interface_config in interfaces.items():
        if interface_config.get('eni_id') == eni_id_to_find:
            return interface
    return None


def log_arguments(op, in_int, out_int, eni_id):
    journal.send(f'Op is "{op}", In Int is "{in_int}", Out Int is "{out_int}", ENI is "{eni_id}"', SYSLOG_IDENTIFIER=my_name)


def rename_interface(old_name, new_name):
    journal.send(f'ip link set dev gwi-{old_name} name {new_name}', SYSLOG_IDENTIFIER=my_name)
    rc, out = rc_cmd(f'ip link set dev gwi-{old_name} name {new_name}')
    if rc != 0:
        journal.send(out, SYSLOG_IDENTIFIER=my_name)


if __name__ == '__main__':
    if len(sys.argv) < 5:
        journal.send('Not enough arguments provided.', SYSLOG_IDENTIFIER=my_name)
        journal.send('Usage: python3 vyos-aws-gwlbtun.py op in_int out_int eni_id', SYSLOG_IDENTIFIER=my_name)
        sys.exit(1)

    op = sys.argv[1]
    in_int = sys.argv[2]
    out_int = sys.argv[3]
    eni_id = sys.argv[4]

    base = ['service', 'aws', 'glb']
    conf = ConfigTreeQuery()
    aws_config = conf.get_config_dict(base, key_mangling=('-', '_'),
                                     get_first_key=True,
                                     no_tag_node_value_mangle=True)

    log_arguments(op, in_int, out_int, eni_id)

    interface = find_interface_by_eni_id(eni_id, aws_config)
    if interface:
        rename_interface(in_int, interface)
