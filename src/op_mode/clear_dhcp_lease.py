#!/usr/bin/env python3
#
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

import argparse
import re

from vyos.configquery import ConfigTreeQuery
from vyos.kea import kea_parse_leases
from vyos.utils.io import ask_yes_no
from vyos.utils.process import call
from vyos.utils.commit import commit_in_progress

# TODO: Update to use Kea control socket command "lease4-del"

config = ConfigTreeQuery()
base = ['service', 'dhcp-server']
lease_file = '/config/dhcp/dhcp4-leases.csv'


def del_lease_ip(address):
    """
    Read lease_file and write data to this file
    without specific section "lease ip"
    Delete section "lease x.x.x.x { x;x;x; }"
    """
    with open(lease_file, encoding='utf-8') as f:
        data = f.read().rstrip()
        pattern = rf"^{address},[^\n]+\n"
        # Delete lease for ip block
        data = re.sub(pattern, '', data)

    # Write new data to original lease_file
    with open(lease_file, 'w', encoding='utf-8') as f:
        f.write(data)

def is_ip_in_leases(address):
    """
    Return True if address found in the lease file
    """
    leases = kea_parse_leases(lease_file)
    for lease in leases:
        if address == lease['address']:
            return True
    print(f'Address "{address}" not found in "{lease_file}"')
    return False

if not config.exists(base):
    print('DHCP-server not configured!')
    exit(0)

if config.exists(base + ['failover']):
    print('Lease cannot be reset in failover mode!')
    exit(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ip', help='IPv4 address', action='store', required=True)

    args = parser.parse_args()
    address = args.ip

    if not is_ip_in_leases(address):
        exit(1)

    if commit_in_progress():
        print('Cannot clear DHCP lease while a commit is in progress')
        exit(1)

    if not ask_yes_no(f'This will restart DHCP server.\nContinue?'):
        exit(1)
    else:
        del_lease_ip(address)
        call('systemctl restart kea-dhcp4-server.service')
