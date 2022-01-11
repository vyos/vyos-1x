#!/usr/bin/env python3
#
# Copyright (C) 2020-2021 VyOS maintainers and contributors
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
from copy import deepcopy

from vyos.config import Config
from vyos.util import write_file
from vyos import ConfigError
from vyos import airbag
airbag.enable()

try:
    with open('/usr/share/vyos/default_motd') as f:
        motd = f.read()
except:
    # Use an empty banner if the default banner file cannot be read
    motd = "\n"

PRELOGIN_FILE = r'/etc/issue'
PRELOGIN_NET_FILE = r'/etc/issue.net'
POSTLOGIN_FILE = r'/etc/motd'

default_config_data = {
    'issue': 'Welcome to VyOS - \\n \\l\n\n',
    'issue_net': '',
    'motd': motd
}

def get_config(config=None):
    banner = deepcopy(default_config_data)
    if config:
        conf = config
    else:
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
            # always add newline character
            tmp += '\n'
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
            # always add newline character
            tmp += '\n'
        else:
            tmp = ''

        banner['issue'] = banner['issue_net'] = tmp

    return banner

def verify(banner):
    pass

def generate(banner):
    pass

def apply(banner):
    write_file(PRELOGIN_FILE, banner['issue'])
    write_file(PRELOGIN_NET_FILE, banner['issue_net'])
    write_file(POSTLOGIN_FILE, banner['motd'])

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
