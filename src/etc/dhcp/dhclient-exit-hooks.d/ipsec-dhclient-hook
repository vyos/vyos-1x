#!/usr/bin/env python3

import os
import sys

from vyos.util import call

IPSEC_CONF="/etc/ipsec.conf"
IPSEC_SECRETS="/etc/ipsec.secrets"

def getlines(file):
    with open(file, 'r') as f:
        return f.readlines()

def writelines(file, lines):
    with open(file, 'w') as f:
        f.writelines(lines)

if __name__ == '__main__':
    interface = os.getenv('interface')
    new_ip = os.getenv('new_ip_address')
    old_ip = os.getenv('old_ip_address')
    reason = os.getenv('reason')

    if (old_ip == new_ip and reason != 'BOUND') or reason in ['REBOOT', 'EXPIRE']:
        sys.exit(0)

    conf_lines = getlines(IPSEC_CONF)
    secrets_lines = getlines(IPSEC_SECRETS)
    found = False
    to_match = f'# dhcp:{interface}'

    for i, line in enumerate(conf_lines):
        if line.find(to_match) > 0:
            conf_lines[i] = line.replace(old_ip, new_ip)
            found = True

    for i, line in enumerate(secrets_lines):
        if line.find(to_match) > 0:
            secrets_lines[i] = line.replace(old_ip, new_ip)

    if found:
        writelines(IPSEC_CONF, conf_lines)
        writelines(IPSEC_SECRETS, secrets_lines)
        call('sudo /usr/sbin/ipsec rereadall')
        call('sudo /usr/sbin/ipsec reload')
