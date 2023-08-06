#!/usr/bin/env python3
#
# Copyright (C) 2018-2022 VyOS maintainers and contributors
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

from socket import gethostname
from sys import exit
from urllib3 import PoolManager

from vyos.base import Warning
from vyos.config import Config
from vyos.configverify import verify_interface_exists
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.permission import chown
from vyos import ConfigError

from vyos import airbag
airbag.enable()

config_file = r'/etc/salt/minion'
master_keyfile = r'/opt/vyatta/etc/config/salt/pki/minion/master_sign.pub'

user='minion'
group='vyattacfg'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'salt-minion']

    if not conf.exists(base):
        return None

    salt = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    # ID default is dynamic thus we can not use defaults()
    if 'id' not in salt:
        salt['id'] = gethostname()
    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    salt = conf.merge_defaults(salt, recursive=True)

    if not conf.exists(base):
        return None
    else:
        conf.set_level(base)

    return salt

def verify(salt):
    if not salt:
        return None

    if 'hash' in salt and salt['hash'] == 'sha1':
        Warning('Do not use sha1 hashing algorithm, upgrade to sha256 or later!')

    if 'source_interface' in salt:
        verify_interface_exists(salt['source_interface'])

    return None

def generate(salt):
    if not salt:
        return None

    render(config_file, 'salt-minion/minion.j2', salt, user=user, group=group)

    if not os.path.exists(master_keyfile):
        if 'master_key' in salt:
            req = PoolManager().request('GET', salt['master_key'], preload_content=False)
            with open(master_keyfile, 'wb') as f:
                while True:
                    data = req.read(1024)
                    if not data:
                        break
                    f.write(data)

            req.release_conn()
            chown(master_keyfile, user, group)

    return None

def apply(salt):
    service_name = 'salt-minion.service'
    if not salt:
        # Salt removed from running config
        call(f'systemctl stop {service_name}')
        if os.path.exists(config_file):
            os.unlink(config_file)
    else:
        call(f'systemctl restart {service_name}')

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
