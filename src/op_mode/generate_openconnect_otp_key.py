#!/usr/bin/env python3
#
# Copyright (C) 2022-2023 VyOS maintainers and contributors
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
import os

from vyos.utils.process import popen
from secrets import token_hex
from base64 import b32encode

if os.geteuid() != 0:
    exit("You need to have root privileges to run this script.\nPlease try again, this time using 'sudo'. Exiting.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--username", type=str, help='Username used for authentication', required=True)
    parser.add_argument("-i", "--interval", type=str, help='Duration of single time interval',  default="30", required=False)
    parser.add_argument("-d", "--digits", type=str, help='The number of digits in the one-time password', default="6", required=False)
    args = parser.parse_args()

    hostname = os.uname()[1]
    username = args.username
    digits = args.digits
    period = args.interval

    # check variables:
    if int(digits) < 6 or int(digits) > 8:
        print("")
        quit("The number of digits in the one-time password must be between '6' and '8'")

    if int(period) < 5 or int(period) > 86400:
        print("")
        quit("Time token interval must be between '5' and '86400' seconds")

    # generate OTP key, URL & QR:
    key_hex = token_hex(20)
    key_base32 = b32encode(bytes.fromhex(key_hex)).decode()

    otp_url=''.join(["otpauth://totp/",username,"@",hostname,"?secret=",key_base32,"&digits=",digits,"&period=",period])
    qrcode,err = popen('qrencode -t ansiutf8', input=otp_url)

    print("# You can share it with the user, he just needs to scan the QR in his OTP app")
    print("# username: ", username)
    print("# OTP KEY: ", key_base32)
    print("# OTP URL: ", otp_url)
    print(qrcode)
    print('# To add this OTP key to configuration, run the following commands:')
    print(f"set vpn openconnect authentication local-users username {username} otp key '{key_hex}'")
    if period != "30":
        print(f"set vpn openconnect authentication local-users username {username} otp interval '{period}'")
    if digits != "6":
        print(f"set vpn openconnect authentication local-users username {username} otp otp-length '{digits}'")
