#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
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
#

import sys
import os
import re
import argparse
import subprocess
from vyos.config import Config

def detect_qat_dev():
    ret = subprocess.Popen(['sudo', 'lspci',  '-nn'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (output, err) = ret.communicate()
    if not err:
        data = re.findall('(8086:19e2)|(8086:37c8)|(8086:0435)|(8086:6f54)', output.decode("utf-8"))
        #If QAT devices found
        if data:
            return
    print("\t No QAT device found")
    sys.exit(1)

def show_qat_status():
    detect_qat_dev()

    # Check QAT service
    if not os.path.exists('/etc/init.d/vyos-qat-utilities'):
        print("\t QAT service not installed")
        sys.exit(1)

    # Show QAT service
    os.system('sudo /etc/init.d/vyos-qat-utilities status')

# Return QAT devices
def get_qat_devices():
    ret = subprocess.Popen(['sudo', '/etc/init.d/vyos-qat-utilities',  'status'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (output, err) = ret.communicate()
    if not err:
        #print(output)
        data_st = output.decode("utf-8")
        elm_lst = re.findall('qat_dev\d', data_st)
        print('\n'.join(elm_lst))

# Return QAT path in sysfs
def get_qat_proc_path(qat_dev):
    q_type = ""
    q_bsf  = ""
    ret = subprocess.Popen(['sudo', '/etc/init.d/vyos-qat-utilities',  'status'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (output, err) = ret.communicate()
    if not err:
        # Parse QAT service output
        data_st = output.decode("utf-8").split("\n")
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
        return "/sys/kernel/debug/qat_"+q_type+"_"+q_bsf+"/"

# Check if QAT service confgured
def check_qat_if_conf():
    if not Config().exists_effective('system acceleration qat'):
        print("\t system acceleration qat is not configured")
        sys.exit(1)

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("--hw", action="store_true", help="Show Intel QAT HW")
group.add_argument("--dev_list", action="store_true", help="Return Intel QAT devices")
group.add_argument("--flow", action="store_true", help="Show Intel QAT flows")
group.add_argument("--interrupts", action="store_true", help="Show Intel QAT interrupts")
group.add_argument("--status", action="store_true", help="Show Intel QAT status")
group.add_argument("--conf", action="store_true", help="Show Intel QAT configuration")

parser.add_argument("--dev", type=str, help="Selected QAT device")

args = parser.parse_args()

if args.hw:
    detect_qat_dev()
    # Show availible Intel QAT devices
    os.system('sudo lspci -nn | egrep -e \'8086:37c8|8086:19e2|8086:0435|8086:6f54\'')
elif args.flow and args.dev:
    check_qat_if_conf()
    os.system('sudo cat '+get_qat_proc_path(args.dev)+"fw_counters")
elif args.interrupts:
    check_qat_if_conf()
    # Delete _dev from args.dev
    os.system('sudo cat /proc/interrupts | grep qat')
elif args.status:
    check_qat_if_conf()
    show_qat_status()
elif args.conf and args.dev:
    check_qat_if_conf()
    os.system('sudo cat '+get_qat_proc_path(args.dev)+"dev_cfg")
elif args.dev_list:
    get_qat_devices()
else:
    parser.print_help()
    sys.exit(1)