#!/usr/bin/env python3
#
# Copyright (C) 2019-2023 VyOS maintainers and contributors
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
import re

from sys import exit

from vyos.config import Config
from vyos.utils.process import popen
from vyos.utils.process import run
from vyos import ConfigError
from vyos import airbag
airbag.enable()

qat_init_script = '/etc/init.d/qat_service'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    data = {}

    if conf.exists(['system', 'acceleration', 'qat']):
        data.update({'qat_enable' : ''})

    if conf.exists(['vpn', 'ipsec']):
        data.update({'ipsec' : ''})

    if conf.exists(['interfaces', 'openvpn']):
        data.update({'openvpn' : ''})

    return data


def vpn_control(action, force_ipsec=False):
    # XXX: Should these commands report failure?
    if action == 'restore' and force_ipsec:
        return run('ipsec start')

    return run(f'ipsec {action}')


def verify(qat):
    if 'qat_enable' not in qat:
        return

    # Check if QAT service installed
    if not os.path.exists(qat_init_script):
        raise ConfigError('QAT init script not found')

    # Check if QAT device exist
    output, err = popen('lspci -nn', decode='utf-8')
    if not err:
        # PCI id | Chipset
        # 19e2 -> C3xx
        # 37c8 -> C62x
        # 0435 -> DH895
        # 6f54 -> D15xx
        # 18ee -> QAT_200XX
        data = re.findall(
            '(8086:19e2)|(8086:37c8)|(8086:0435)|(8086:6f54)|(8086:18ee)', output)
        # If QAT devices found
        if not data:
            raise ConfigError('No QAT acceleration device found')

def apply(qat):
    # Shutdown VPN service which can use QAT
    if 'ipsec' in qat:
        vpn_control('stop')

    # Enable/Disable QAT service
    if 'qat_enable' in qat:
        run(f'{qat_init_script} start')
    else:
        run(f'{qat_init_script} stop')

    # Recover VPN service
    if 'ipsec' in qat:
        vpn_control('start')


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        apply(c)
    except ConfigError as e:
        print(e)
        vpn_control('restore', force_ipsec=('ipsec' in c))
        exit(1)
