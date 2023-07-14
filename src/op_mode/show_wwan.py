#!/usr/bin/env python3
#
# Copyright (C) 2021-2023 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse

from sys import exit
from vyos.configquery import ConfigTreeQuery
from vyos.utils.process import cmd

parser = argparse.ArgumentParser()
parser.add_argument("--model", help="Get module model", action="store_true")
parser.add_argument("--revision", help="Get module revision", action="store_true")
parser.add_argument("--capabilities", help="Get module capabilities", action="store_true")
parser.add_argument("--imei", help="Get module IMEI/ESN/MEID", action="store_true")
parser.add_argument("--imsi", help="Get module IMSI", action="store_true")
parser.add_argument("--msisdn", help="Get module MSISDN", action="store_true")
parser.add_argument("--sim", help="Get SIM card status", action="store_true")
parser.add_argument("--signal", help="Get current RF signal info", action="store_true")
parser.add_argument("--firmware", help="Get current RF signal info", action="store_true")

required = parser.add_argument_group('Required arguments')
required.add_argument("--interface", help="WWAN interface name, e.g. wwan0", required=True)

def qmi_cmd(device, command, silent=False):
    try:
        tmp = cmd(f'qmicli --device={device} --device-open-proxy {command}')
        tmp = tmp.replace(f'[{cdc}] ', '')
        if not silent:
            # skip first line as this only holds the info headline
            for line in tmp.splitlines()[1:]:
                print(line.lstrip())
        return tmp
    except:
        print('Command not supported by Modem')
        exit(1)

if __name__ == '__main__':
    args = parser.parse_args()

    tmp = ConfigTreeQuery()
    if not tmp.exists(['interfaces', 'wwan', args.interface]):
        print(f'Interface "{args.interface}" unconfigured!')
        exit(1)

    # remove the WWAN prefix from the interface, required for the CDC interface
    if_num = args.interface.replace('wwan','')
    cdc = f'/dev/cdc-wdm{if_num}'

    if args.model:
        qmi_cmd(cdc, '--dms-get-model')
    elif args.capabilities:
        qmi_cmd(cdc, '--dms-get-capabilities')
        qmi_cmd(cdc, '--dms-get-band-capabilities')
    elif args.revision:
        qmi_cmd(cdc, '--dms-get-revision')
    elif args.imei:
        qmi_cmd(cdc, '--dms-get-ids')
    elif args.imsi:
        qmi_cmd(cdc, '--dms-uim-get-imsi')
    elif args.msisdn:
        qmi_cmd(cdc, '--dms-get-msisdn')
    elif args.sim:
        qmi_cmd(cdc, '--uim-get-card-status')
    elif args.signal:
        qmi_cmd(cdc, '--nas-get-signal-info')
        qmi_cmd(cdc, '--nas-get-rf-band-info')
    elif args.firmware:
        tmp = qmi_cmd(cdc, '--dms-get-manufacturer', silent=True)
        if 'Sierra Wireless' in tmp:
            qmi_cmd(cdc, '--dms-swi-get-current-firmware')
        else:
            qmi_cmd(cdc, '--dms-get-software-version')
    else:
        parser.print_help()
        exit(1)
