#!/usr/bin/env python3
#
# Copyright (C) 2018-2020 VyOS maintainers and contributors
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

from copy import deepcopy
from socket import gethostname
from sys import exit
from urllib3 import PoolManager

from vyos.config import Config
from vyos.template import render
from vyos.command import call, chown
from vyos import ConfigError

config_file = r'/etc/salt/minion'
master_keyfile = r'/opt/vyatta/etc/config/salt/pki/minion/master_sign.pub'

default_config_data = {
    'hash': 'sha256',
    'log_level': 'warning',
    'master' : 'salt',
    'user': 'minion',
    'group': 'vyattacfg',
    'salt_id': gethostname(),
    'mine_interval': '60',
    'verify_master_pubkey_sign': 'false',
    'master_key': ''
}

def get_config():
    salt = deepcopy(default_config_data)
    conf = Config()
    base = ['service', 'salt-minion']

    if not conf.exists(base):
        return None
    else:
        conf.set_level(base)

    if conf.exists(['hash']):
        salt['hash'] = conf.return_value(['hash'])

    if conf.exists(['master']):
        salt['master'] = conf.return_values(['master'])

    if conf.exists(['id']):
        salt['salt_id'] = conf.return_value(['id'])

    if conf.exists(['user']):
        salt['user'] = conf.return_value(['user'])

    if conf.exists(['interval']):
        salt['interval'] = conf.return_value(['interval'])

    if conf.exists(['master-key']):
        salt['master_key'] = conf.return_value(['master-key'])
        salt['verify_master_pubkey_sign'] = 'true'

    return salt

def verify(salt):
    return None

def generate(salt):
    if not salt:
        return None

    render(config_file, 'salt-minion/minion.tmpl', salt,
           user=salt['user'], group=salt['group'])

    if not os.path.exists(master_keyfile):
        if salt['master_key']:
            req = PoolManager().request('GET', salt['master_key'], preload_content=False)

            with open(master_keyfile, 'wb') as f:
                while True:
                    data = req.read(1024)
                    if not data:
                        break
                    f.write(data)

            req.release_conn()
            chown(master_keyfile, salt['user'], salt['group'])

    return None

def apply(salt):
    if not salt:
        # Salt removed from running config
        call('systemctl stop salt-minion.service')
        if os.path.exists(config_file):
            os.unlink(config_file)
    else:
        call('systemctl restart salt-minion.service')

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
