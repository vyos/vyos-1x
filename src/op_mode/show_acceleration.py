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

import sys
import os
import re
import argparse

from tabulate import tabulate

from vyos import qat
from vyos.config import Config
from vyos.utils.process import call
from vyos.utils.process import popen

qat_init_script = '/etc/init.d/qat_service'


def detect_qat_dev():
    """Exit unless a QAT device is present on the PCI bus."""
    devices = qat.find_devices()
    if devices:
        return devices

    print('No QAT device found')
    sys.exit(1)


def is_configured():
    return Config().exists_effective('system acceleration qat')


def show_qat_status():
    """Report the state of every QAT device as the kernel sees it.

    The QAT modules autoload from the PCI modalias and the device is started
    by the driver, neither of which depends on 'system acceleration qat'.
    Report what the kernel is actually doing, not what the configuration says
    it should be doing.
    """
    devices = detect_qat_dev()

    print('Intel QAT\n')
    print(
        tabulate(
            [
                [
                    device['address'],
                    device['chipset'],
                    device['driver'] if device['driver'] else 'none',
                    qat.get_device_state(device),
                ]
                for device in devices
            ],
            headers=['PCI address', 'Chipset', 'Driver', 'State'],
        )
    )

    algorithms = qat.get_crypto_algorithms()
    configured = is_configured()

    count = len(algorithms)
    state = 'set' if configured else 'not set'

    print()
    print(f'Kernel crypto framework:  {count} algorithm(s) registered by QAT')
    print(f"Configuration:            'system acceleration qat' is {state}")

    if algorithms and not configured:
        print(
            "\nWARNING: QAT is registered with the kernel crypto framework but\n"
            "         'system acceleration qat' is not set. The kernel modules\n"
            '         autoload from the PCI modalias and the device is started by\n'
            '         the driver, both independently of the configuration, so\n'
            '         cryptographic operations - IPsec ESP among them - may still\n'
            '         be offloaded to the QAT device.'
        )

    # The Intel userspace tooling reports additional detail when it is present.
    # It is not required for any of the above.
    if os.path.exists(qat_init_script):
        print()
        call(f'{qat_init_script} status')


# Return QAT devices
def get_qat_devices():
    data_st, err = popen(f'{qat_init_script} status', decode='utf-8')
    if not err:
        elm_lst = re.findall(r'qat_dev\d', data_st)
        print('\n'.join(elm_lst))


# Return QAT path in sysfs
def get_qat_proc_path(qat_dev):
    q_type = ""
    q_bsf  = ""
    output, err = popen(f'{qat_init_script} status', decode='utf-8')
    if not err:
        # Parse QAT service output
        data_st = output.split("\n")
        for elm_str in range(len(data_st)):
            if re.search(qat_dev, data_st[elm_str]):
                elm_list = data_st[elm_str].split(", ")
                for elm in range(len(elm_list)):
                    if re.search('type', elm_list[elm]):
                        q_list = elm_list[elm].split(": ")
                        q_type=q_list[1]
                    elif re.search('bsf', elm_list[elm]):
                        q_list = elm_list[elm].split(": ")
                        q_bsf = q_list[1]
        if q_type and q_bsf:
            return f'/sys/kernel/debug/qat_{q_type}_{q_bsf}/'

    print(f'Could not determine the debugfs path for {qat_dev}')
    sys.exit(1)


parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("--hw", action="store_true", help="Show Intel QAT HW")
group.add_argument("--dev-list", action="store_true", help="Return Intel QAT devices")
group.add_argument("--flow", action="store_true", help="Show Intel QAT flows")
group.add_argument("--interrupts", action="store_true", help="Show Intel QAT interrupts")
group.add_argument("--status", action="store_true", help="Show Intel QAT status")
group.add_argument("--conf", action="store_true", help="Show Intel QAT configuration")

parser.add_argument("--dev", type=str, help="Selected QAT device")

args = parser.parse_args()

if args.hw:
    detect_qat_dev()
    # Show available Intel QAT devices. The device IDs come from the single
    # table in vyos.qat so that this filter cannot drift away from the one
    # used for detection.
    device_filter = '|'.join(f'8086:{i[2:]}' for i in sorted(qat.PCI_DEVICE_IDS))
    call(f"lspci -nn | egrep -e '{device_filter}'")
elif args.flow and args.dev:
    detect_qat_dev()
    call('cat '+get_qat_proc_path(args.dev)+"fw_counters")
elif args.interrupts:
    detect_qat_dev()
    # Delete _dev from args.dev
    call('cat /proc/interrupts | grep qat')
elif args.status:
    show_qat_status()
elif args.conf and args.dev:
    detect_qat_dev()
    call('cat '+get_qat_proc_path(args.dev)+"dev_cfg")
elif args.dev_list:
    get_qat_devices()
else:
    parser.print_help()
    sys.exit(1)
