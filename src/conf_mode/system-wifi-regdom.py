#!/usr/bin/env python3
#
# Copyright (C) 2019-2020 VyOS maintainers and contributors
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
from sys import exit

from vyos.config import Config
from vyos import ConfigError
from vyos.template import render


config_80211_file='/etc/modprobe.d/cfg80211.conf'
config_crda_file='/etc/default/crda'

default_config_data = {
    'regdom' : '',
    'deleted' : False
}

def get_config():
    regdom = deepcopy(default_config_data)
    conf = Config()
    base = ['system', 'wifi-regulatory-domain']

    # Check if interface has been removed
    if not conf.exists(base):
        regdom['deleted'] = True
        return regdom
    else:
        regdom['regdom'] = conf.return_value(base)

    return regdom

def verify(regdom):
    if regdom['deleted']:
        return None

    if not regdom['regdom']:
        raise ConfigError("Wireless regulatory domain is mandatory.")

    return None

def generate(regdom):
    print("Changing the wireless regulatory domain requires a system reboot.")

    if regdom['deleted']:
        if os.path.isfile(config_80211_file):
            os.unlink(config_80211_file)

        if os.path.isfile(config_crda_file):
            os.unlink(config_crda_file)

        return None

    render(config_80211_file, 'wifi/cfg80211.conf.tmpl', regdom)
    render(config_crda_file, 'wifi/crda.tmpl', regdom)
    return None

def apply(regdom):
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
