#!/usr/bin/env python3
#
# Copyright (C) 2018-2021 VyOS maintainers and contributors
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

from vyos.config import Config
from vyos.configverify import verify_vrf
from vyos import ConfigError
from vyos.util import call
from vyos.template import render
from vyos import airbag
airbag.enable()

config_file = r'/run/ntpd/ntpd.conf'
systemd_override = r'/etc/systemd/system/ntp.service.d/override.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'ntp']
    if not conf.exists(base):
        return None

    ntp = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    ntp['config_file'] = config_file
    return ntp

def verify(ntp):
    # bail out early - looks like removal from running config
    if not ntp:
        return None

    if 'allow_clients' in ntp and 'server' not in ntp:
        raise ConfigError('NTP server not configured')

    verify_vrf(ntp)
    return None

def generate(ntp):
    # bail out early - looks like removal from running config
    if not ntp:
        return None

    render(config_file, 'ntp/ntpd.conf.tmpl', ntp)
    render(systemd_override, 'ntp/override.conf.tmpl', ntp)

    return None

def apply(ntp):
    if not ntp:
        # NTP support is removed in the commit
        call('systemctl stop ntp.service')
        if os.path.exists(config_file):
            os.unlink(config_file)
        if os.path.isfile(systemd_override):
            os.unlink(systemd_override)

    # Reload systemd manager configuration
    call('systemctl daemon-reload')
    if ntp:
        call('systemctl restart ntp.service')

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
