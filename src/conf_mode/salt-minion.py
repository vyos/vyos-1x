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
from jinja2 import FileSystemLoader, Environment
from pwd import getpwnam
from socket import gethostname
from sys import exit
from urllib3 import PoolManager

from vyos.config import Config
from vyos.defaults import directories as vyos_data_dir
from vyos import ConfigError

config_file = r'/etc/salt/minion'

default_config_data = {
    'hash_type': 'sha256',
    'log_file': '/var/log/salt/minion',
    'log_level': 'warning',
    'master' : 'salt',
    'user': 'minion',
    'salt_id': gethostname(),
    'mine_interval': '60',
    'verify_master_pubkey_sign': 'false'
}

def get_config():
    salt = deepcopy(default_config_data)
    conf = Config()
    if not conf.exists('service salt-minion'):
        return None
    else:
        conf.set_level('service salt-minion')

    if conf.exists('hash_type'):
        salt['hash_type'] = conf.return_value('hash_type')

    if conf.exists('log_file'):
        salt['log_file'] = conf.return_value('log_file')

    if conf.exists('log_level'):
        salt['log_level'] = conf.return_value('log_level')

    if conf.exists('master'):
        master = conf.return_values('master')
        salt['master'] = master

    if conf.exists('id'):
        salt['salt_id'] = conf.return_value('id')

    if conf.exists('user'):
        salt['user'] = conf.return_value('user')

    if conf.exists('mine_interval'):
        salt['mine_interval'] = conf.return_value('mine_interval')

    salt['master-key'] = None
    if conf.exists('master-key'):
        salt['master-key'] = conf.return_value('master-key')
        salt['verify_master_pubkey_sign'] = 'true'

    return salt

def generate(salt):
    paths = ['/etc/salt/','/var/run/salt','/opt/vyatta/etc/config/salt/']
    directory = '/opt/vyatta/etc/config/salt/pki/minion'
    uid = getpwnam(salt['user']).pw_uid
    http = PoolManager()

    if salt is None:
        return None

    # Prepare Jinja2 template loader from files
    tmpl_path = os.path.join(vyos_data_dir['data'], 'templates', 'salt-minion')
    fs_loader = FileSystemLoader(tmpl_path)
    env = Environment(loader=fs_loader)

    if not os.path.exists(directory):
        os.makedirs(directory)

    tmpl = env.get_template('minion.tmpl')
    config_text = tmpl.render(salt)
    with open(config_file, 'w') as f:
        f.write(config_text)

    path = "/etc/salt/"
    for path in paths:
      for root, dirs, files in os.walk(path):
        for usgr in dirs:
          os.chown(os.path.join(root, usgr), uid, 100)
        for usgr in files:
          os.chown(os.path.join(root, usgr), uid, 100)

    if not os.path.exists('/opt/vyatta/etc/config/salt/pki/minion/master_sign.pub'):
        if not salt['master-key'] is None:
            r = http.request('GET', salt['master-key'], preload_content=False)

            with open('/opt/vyatta/etc/config/salt/pki/minion/master_sign.pub', 'wb') as out:
                while True:
                    data = r.read(1024)
                    if not data:
                        break
                    out.write(data)

            r.release_conn()

    return None

def apply(salt):
    if salt is not None:
        os.system("sudo systemctl restart salt-minion")
    else:
        # Salt access is removed in the commit
        os.system("sudo systemctl stop salt-minion")
        os.unlink(config_file)

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
