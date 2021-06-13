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

import os

from sys import exit

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configverify import verify_authentication
from vyos.configverify import verify_interface_exists
from vyos.configverify import verify_vrf
from vyos.ifconfig import WWANIf
from vyos.util import cmd
from vyos.template import render
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'wwan']
    wwan = get_interface_dict(conf, base)

    return wwan

def verify(wwan):
    if 'deleted' in wwan:
        return None

    ifname = wwan['ifname']
    if not 'apn' in wwan:
        raise ConfigError(f'No APN configured for "{ifname}"!')

    verify_interface_exists(ifname)
    verify_authentication(wwan)
    verify_vrf(wwan)

    return None

def generate(wwan):
    return None

def apply(wwan):
    # we only need the modem number. wwan0 -> 0, wwan1 -> 1
    modem = wwan['ifname'].lstrip('wwan')
    base_cmd = f'mmcli --modem {modem}'

    w = WWANIf(wwan['ifname'])
    if 'deleted' in wwan or 'disable' in wwan:
        w.remove()
        cmd(f'{base_cmd} --simple-disconnect')
        return None

    options = 'apn=' + wwan['apn']
    if 'authentication' in wwan:
        options += ',user={user},password={password}'.format(**wwan['authentication'])

    command = f'{base_cmd} --simple-connect="{options}"'
    cmd(command)
    w.update(wwan)

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
