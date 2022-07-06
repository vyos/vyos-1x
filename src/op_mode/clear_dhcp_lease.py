#!/usr/bin/env python3

import argparse
import re

from isc_dhcp_leases import Lease
from isc_dhcp_leases import IscDhcpLeases

from vyos.configquery import ConfigTreeQuery
from vyos.util import ask_yes_no
from vyos.util import call
from vyos.util import commit_in_progress


config = ConfigTreeQuery()
base = ['service', 'dhcp-server']
lease_file = '/config/dhcpd.leases'


def del_lease_ip(address):
    """
    Read lease_file and write data to this file
    without specific section "lease ip"
    Delete section "lease x.x.x.x { x;x;x; }"
    """
    with open(lease_file, encoding='utf-8') as f:
        data = f.read().rstrip()
        lease_config_ip = '{(?P<config>[\s\S]+?)\n}'
        pattern = rf"lease {address} {lease_config_ip}"
        # Delete lease for ip block
        data = re.sub(pattern, '', data)

    # Write new data to original lease_file
    with open(lease_file, 'w', encoding='utf-8') as f:
        f.write(data)

def is_ip_in_leases(address):
    """
    Return True if address found in the lease file
    """
    leases = IscDhcpLeases(lease_file)
    lease_ips = []
    for lease in leases.get():
        lease_ips.append(lease.ip)
    if address not in lease_ips:
        print(f'Address "{address}" not found in "{lease_file}"')
        return False
    return True


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
        call('systemctl restart isc-dhcp-server.service')
