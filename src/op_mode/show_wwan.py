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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse

from json import JSONDecodeError
from json import loads
from sys import exit

from vyos.configquery import ConfigTreeQuery
from vyos.utils.dict import dict_search
from vyos.utils.process import is_systemd_service_active
from vyos.utils.process import popen
from vyos.utils.process import STDOUT
from vyos.utils.wwan import modem_index
from vyos.utils.wwan import service_name

parser = argparse.ArgumentParser()
parser.add_argument("--model", help="Get module model", action="store_true")
parser.add_argument("--revision", help="Get module revision", action="store_true")
parser.add_argument("--capabilities", help="Get module capabilities", action="store_true")
parser.add_argument("--imei", help="Get module IMEI/ESN/MEID", action="store_true")
parser.add_argument("--imsi", help="Get module IMSI", action="store_true")
parser.add_argument("--msisdn", help="Get module MSISDN", action="store_true")
parser.add_argument("--sim", help="Get SIM card status", action="store_true")
parser.add_argument("--signal", help="Get current RF signal info", action="store_true")
parser.add_argument("--firmware", help="Get module firmware information", action="store_true")

required = parser.add_argument_group('Required arguments')
required.add_argument("--interface", help="WWAN interface name, e.g. wwan0", required=True)

def mmcli(*args: str) -> dict:
    """ Query ModemManager and return its answer as a dictionary.

    ModemManager has already probed the modem and speaks whatever control
    protocol it exposes - QMI, MBIM or plain AT - so this works on every modem
    we support. Talking to /dev/cdc-wdmN directly does not: it assumes the
    modem offers a QMI control port, and an MBIM modem only answers with a
    CID allocation timeout after several seconds.
    """
    if not is_systemd_service_active(service_name):
        raise ValueError('ModemManager is not running, no modem can be queried')

    # mmcli reports why a modem did not answer on stderr - fold it into the
    # output so it can be handed to the operator verbatim
    tmp, code = popen(['mmcli', '--output-json', *args], shell=False, stderr=STDOUT)
    if code != 0:
        raise ValueError(tmp.strip() or
                         f'ModemManager query failed with exit code {code}')

    try:
        return loads(tmp)
    except JSONDecodeError as e:
        raise ValueError(f'Malformed answer from ModemManager: {e}') from e

def modem_info(ifname: str) -> dict:
    """ Return everything ModemManager knows about the modem behind ifname """
    return mmcli('--modem', modem_index(ifname))['modem']

def sim_info(modem: dict) -> dict:
    """ Return the properties of the SIM card inserted into a modem """
    sim = dict_search('generic.sim', modem)
    if not sim or sim == '--':
        raise ValueError('No SIM card inserted')
    return mmcli('--sim', sim.split('/')[-1])['sim']['properties']

def format_value(value) -> str:
    # ModemManager renders an unset scalar as "--" and an unset list as an
    # empty one - neither is useful to read
    if isinstance(value, list):
        return ', '.join(str(v) for v in value) if value else 'n/a'
    if value in (None, '', '--'):
        return 'n/a'
    return str(value)

def show(data: dict, fields: dict) -> None:
    """ Print a "Description: value" block, one field per line. Every field maps
    to the dotted path of its value, optionally followed by "|" and the unit to
    append to it. """
    width = max(len(field) for field in fields) + 2
    for field, path in fields.items():
        path, _, unit = path.partition('|')
        value = format_value(dict_search(path, data))
        if unit and value != 'n/a':
            value += unit
        print(f'{field + ":":<{width}}{value}')

def main():
    args = parser.parse_args()

    conf = ConfigTreeQuery()
    if not conf.exists(['interfaces', 'wwan', args.interface]):
        print(f'Interface "{args.interface}" unconfigured!')
        exit(1)

    modem = modem_info(args.interface)

    if args.model:
        show(modem, {'Manufacturer': 'generic.manufacturer',
                     'Model': 'generic.model',
                     'Hardware revision': 'generic.hardware-revision'})
    elif args.revision:
        show(modem, {'Firmware revision': 'generic.revision',
                     'Hardware revision': 'generic.hardware-revision',
                     'Carrier configuration': 'generic.carrier-configuration'})
    elif args.capabilities:
        show(modem, {'Current capabilities': 'generic.current-capabilities',
                     'Supported capabilities': 'generic.supported-capabilities',
                     'Current bands': 'generic.current-bands',
                     'Supported bands': 'generic.supported-bands',
                     'Current modes': 'generic.current-modes',
                     'Supported IP families': 'generic.supported-ip-families'})
    elif args.imei:
        show(modem, {'IMEI': '3gpp.imei',
                     'Equipment identifier': 'generic.equipment-identifier'})
    elif args.imsi:
        show(sim_info(modem), {'IMSI': 'imsi'})
    elif args.msisdn:
        show(modem, {'MSISDN': 'generic.own-numbers'})
    elif args.sim:
        show(sim_info(modem), {'Operator': 'operator-name',
                               'Operator code': 'operator-code',
                               'ICCID': 'iccid',
                               'IMSI': 'imsi',
                               'Active': 'active'})
    elif args.signal:
        # ModemManager only exposes RSRP/RSRQ/SNR through its extended signal
        # API, which has to be armed with "mmcli --signal-setup" first - a
        # persistent change to the modem we have no business making from a
        # "show" command, and one plenty of modems do not support at all.
        show(modem, {'Access technology': 'generic.access-technologies',
                     'Signal quality': 'generic.signal-quality.value|%',
                     'Operator': '3gpp.operator-name',
                     'Registration': '3gpp.registration-state',
                     'Packet service': '3gpp.packet-service-state',
                     'State': 'generic.state'})
    elif args.firmware:
        show(modem, {'Firmware revision': 'generic.revision',
                     'Carrier configuration': 'generic.carrier-configuration',
                     'Carrier configuration revision': 'generic.carrier-configuration-revision'})
    else:
        parser.print_help()
        exit(1)

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as e:
        # Do not swallow the reason - a modem that is not answering, a missing
        # SIM and a ModemManager that is not running all used to surface as the
        # very same "Command not supported by Modem"
        print(e)
        exit(1)
