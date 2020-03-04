#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

from sys import exit
from vyos.config import Config
from vyos import ConfigError

motd="""
The programs included with the Debian GNU/Linux system are free software;
the exact distribution terms for each program are described in the
individual files in /usr/share/doc/*/copyright.

Debian GNU/Linux comes with ABSOLUTELY NO WARRANTY, to the extent
permitted by applicable law.
"""

PRELOGIN_FILE = r'/etc/issue'
PRELOGIN_NET_FILE = r'/etc/issue.net'
POSTLOGIN_FILE = r'/etc/motd'

default_config_data = {
    'issue': 'Welcome to VyOS - \n \l',
    'issue_net': 'Welcome to VyOS',
    'motd': motd
}

def get_config():
    banner = default_config_data
    conf = Config()
    base_level = ['system', 'login', 'banner']

    if not conf.exists(base_level):
        return banner
    else:
        conf.set_level(base_level)

    # Post-Login banner
    if conf.exists(['post-login']):
        tmp = conf.return_value(['post-login'])
        # post-login banner can be empty as well
        if tmp:
            tmp = tmp.replace('\\n','\n')
            tmp = tmp.replace('\\t','\t')
        else:
            tmp = ''

        banner['motd'] = tmp

    # Pre-Login banner
    if conf.exists(['pre-login']):
        tmp = conf.return_value(['pre-login'])
        # pre-login banner can be empty as well
        if tmp:
            tmp = tmp.replace('\\n','\n')
            tmp = tmp.replace('\\t','\t')
        else:
            tmp = ''

        banner['issue'] = banner['issue_net'] = tmp

    return banner

def verify(banner):
    pass

def generate(banner):
    pass

def apply(banner):
    with open(PRELOGIN_FILE, 'w') as f:
        f.write(banner['issue'])

    with open(PRELOGIN_NET_FILE, 'w') as f:
        f.write(banner['issue_net'])

    with open(POSTLOGIN_FILE, 'w') as f:
        f.write(banner['motd'])

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
