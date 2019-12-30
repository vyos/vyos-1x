#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
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
from copy import deepcopy
from vyos.config import Config
from vyos import ConfigError

systemd_ctrl_alt_del = '/lib/systemd/system/ctrl-alt-del.target'

default_config_data = {
    'beep_if_fully_booted': False,
    'ctrl_alt_del': 'ignore',
    'reboot_on_panic': True
}

def get_config():
    opt = deepcopy(default_config_data)
    conf = Config()
    conf.set_level('system options')
    if conf.exists(''):
        if conf.exists('ctrl-alt-del-action'):
            opt['ctrl_alt_del'] = conf.return_value('ctrl-alt-del-action')

        opt['beep_if_fully_booted'] = conf.exists('beep-if-fully-booted')
        opt['reboot_on_panic'] = conf.exists('reboot-on-panic')

    return opt

def verify(opt):
    pass

def generate(opt):
    pass

def apply(opt):
    # Beep action
    if opt['beep_if_fully_booted']:
        os.system('systemctl enable vyos-beep.service >/dev/null 2>&1')
    else:
        os.system('systemctl disable vyos-beep.service >/dev/null 2>&1')

    # Ctrl-Alt-Delete action
    if opt['ctrl_alt_del'] == 'ignore':
        if os.path.exists(systemd_ctrl_alt_del):
            os.unlink('/lib/systemd/system/ctrl-alt-del.target')

    elif opt['ctrl_alt_del'] == 'reboot':
        if os.path.exists(systemd_ctrl_alt_del):
            os.unlink(systemd_ctrl_alt_del)
        os.symlink('/lib/systemd/system/reboot.target', systemd_ctrl_alt_del)

    elif opt['ctrl_alt_del'] == 'poweroff':
        if os.path.exists(systemd_ctrl_alt_del):
            os.unlink(systemd_ctrl_alt_del)
        os.symlink('/lib/systemd/system/poweroff.target', systemd_ctrl_alt_del)

    # Reboot system on kernel panic
    with open('/proc/sys/kernel/panic', 'w') as f:
        if opt['reboot_on_panic']:
            f.write('60')
        else:
            f.write('0')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)

