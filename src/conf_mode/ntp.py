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

from vyos.config import Config
from vyos.configverify import verify_vrf
from vyos import ConfigError
from vyos.util import call
from vyos.template import render
from vyos import airbag
airbag.enable()

config_file = r'/etc/ntp.conf'
systemd_override = r'/etc/systemd/system/ntp.service.d/override.conf'

def get_config():
    conf = Config()
    base = ['system', 'ntp']

    ntp = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    return ntp

def verify(ntp):
    # bail out early - looks like removal from running config
    if not ntp:
        return None

    if len(ntp.get('allow_clients', {})) and not (len(ntp.get('server', {})) > 0):
        raise ConfigError('NTP server not configured')

    verify_vrf(ntp)
    return None

def generate(ntp):
    # bail out early - looks like removal from running config
    if not ntp:
        return None

    render(config_file, 'ntp/ntp.conf.tmpl', ntp, trim_blocks=True)
    render(systemd_override, 'ntp/override.conf.tmpl', ntp, trim_blocks=True)

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
