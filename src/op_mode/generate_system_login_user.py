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
    parser.add_argument("-l", "--rate_limit", type=str, help='Limit number of logins (rate-limit) per rate-time (default: 3)',  default="3", required=False)
    parser.add_argument("-t", "--rate_time", type=str, help='Limit number of logins (rate-limit) per rate-time (default: 30)', default="30", required=False)
    parser.add_argument("-w", "--window_size", type=str, help='Set window of concurrently valid codes (default: 3)', default="3", required=False)
    parser.add_argument("-i", "--interval", type=str, help='Duration of single time interval',  default="30", required=False)
    parser.add_argument("-d", "--digits", type=str, help='The number of digits in the one-time password', default="6", required=False)
    args = parser.parse_args()

    hostname = os.uname()[1]
    username = args.username
    rate_limit = args.rate_limit
    rate_time = args.rate_time
    window_size = args.window_size
    digits = args.digits
    period = args.interval

    # check variables:
    if int(rate_limit) < 1 or int(rate_limit) > 10:
        print("")
        quit("Number of logins (rate-limit) must be between '1' and '10'")

    if int(rate_time) < 15 or int(rate_time) > 600:
        print("")
        quit("The rate-time must be between '15' and '600' seconds")

    if int(window_size) < 1 or int(window_size) > 21:
        print("")
        quit("Window of concurrently valid codes must be between '1' and '21' seconds")

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
    print(f"set system login user {username} authentication otp key '{key_base32}'")
    if rate_limit != "3":
        print(f"set system login user {username} authentication otp rate-limit '{rate_limit}'")
    if rate_time != "30":
        print(f"set system login user {username} authentication otp rate-time '{rate_time}'")
    if window_size != "3":
        print(f"set system login user {username} authentication otp window-size '{window_size}'")
