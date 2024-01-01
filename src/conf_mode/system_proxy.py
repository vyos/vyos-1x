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

from sys import exit

from vyos.config import Config
from vyos.template import render
from vyos import ConfigError
from vyos import airbag
airbag.enable()

proxy_def = r'/etc/profile.d/vyos-system-proxy.sh'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'proxy']
    if not conf.exists(base):
        return None

    proxy = conf.get_config_dict(base, get_first_key=True)
    return proxy

def verify(proxy):
    if not proxy:
        return

    if 'url' not in proxy or 'port' not in proxy:
        raise ConfigError('Proxy URL and port require a value')

    if ('username' in proxy and 'password' not in proxy) or \
       ('username' not in proxy and 'password' in proxy):
       raise ConfigError('Both username and password need to be defined!')

def generate(proxy):
    if not proxy:
        if os.path.isfile(proxy_def):
            os.unlink(proxy_def)
        return

    render(proxy_def, 'system/proxy.j2', proxy, permission=0o755)

def apply(proxy):
    pass

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
