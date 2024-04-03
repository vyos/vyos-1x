#!/usr/bin/env python3
#
# Copyright (C) 2018-2024 VyOS maintainers and contributors
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
import pwd

from copy import deepcopy
from glob import glob
from sys import exit

from vyos.base import Warning
from vyos.config import Config
from vyos.configverify import verify_vrf
from vyos.template import render
from vyos.template import is_ipv4
from vyos.utils.process import call
from vyos.utils.permission import chmod_755
from vyos.utils.network import is_addr_assigned
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = r'/etc/default/tftpd'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['service', 'tftp-server']
    if not conf.exists(base):
        return None

    tftpd = conf.get_config_dict(base, key_mangling=('-', '_'),
                                 get_first_key=True,
                                 with_recursive_defaults=True)
    return tftpd

def verify(tftpd):
    # bail out early - looks like removal from running config
    if not tftpd:
        return None

    # Configuring allowed clients without a server makes no sense
    if 'directory' not in tftpd:
        raise ConfigError('TFTP root directory must be configured!')

    if 'listen_address' not in tftpd:
        raise ConfigError('TFTP server listen address must be configured!')

    for address, address_config in tftpd['listen_address'].items():
        if not is_addr_assigned(address):
            Warning(f'TFTP server listen address "{address}" not ' \
                     'assigned to any interface!')
        verify_vrf(address_config)

    return None

def generate(tftpd):
    # cleanup any available configuration file
    # files will be recreated on demand
    for i in glob(config_file + '*'):
        os.unlink(i)

    # bail out early - looks like removal from running config
    if tftpd is None:
        return None

    idx = 0
    for address, address_config in tftpd['listen_address'].items():
        config = deepcopy(tftpd)
        port = tftpd['port']
        if is_ipv4(address):
            config['listen_address'] = f'{address}:{port} -4'
        else:
            config['listen_address'] = f'[{address}]:{port} -6'

        if 'vrf' in address_config:
            config['vrf'] = address_config['vrf']

        file = config_file + str(idx)
        render(file, 'tftp-server/default.j2', config)
        idx = idx + 1

    return None

def apply(tftpd):
    # stop all services first - then we will decide
    call('systemctl stop tftpd@*.service')

    # bail out early - e.g. service deletion
    if tftpd is None:
        return None

    tftp_root = tftpd['directory']
    if not os.path.exists(tftp_root):
        os.makedirs(tftp_root)
        chmod_755(tftp_root)

    # get UNIX uid for user 'tftp'
    tftp_uid = pwd.getpwnam('tftp').pw_uid
    tftp_gid = pwd.getpwnam('tftp').pw_gid

    # get UNIX uid for tftproot directory
    dir_uid = os.stat(tftp_root).st_uid
    dir_gid = os.stat(tftp_root).st_gid

    # adjust uid/gid of tftproot directory if files don't belong to user tftp
    if (tftp_uid != dir_uid) or (tftp_gid != dir_gid):
        os.chown(tftp_root, tftp_uid, tftp_gid)

    idx = 0
    for address in tftpd['listen_address']:
        call(f'systemctl restart tftpd@{idx}.service')
        idx = idx + 1

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
