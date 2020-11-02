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

from netifaces import interfaces
from sys import exit

from vyos.config import Config
from vyos.template import render
from vyos.util import call
from vyos.validate import is_addr_assigned
from vyos import ConfigError
from vyos import airbag
airbag.enable()

curlrc_config = r'/etc/curlrc'
ssh_config = r'/etc/ssh/ssh_config'
systemd_action_file = '/lib/systemd/system/ctrl-alt-del.target'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'options']
    options = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    return options

def verify(options):
    if 'http_client' in options:
        config = options['http_client']
        if 'source_interface' in config:
            if not config['source_interface'] in interfaces():
                raise ConfigError(f'Source interface {source_interface} does not '
                                  f'exist'.format(**config))

        if {'source_address', 'source_interface'} <= set(config):
            raise ConfigError('Can not define both HTTP source-interface and source-address')

        if 'source_address' in config:
            if not is_addr_assigned(config['source_address']):
                raise ConfigError('No interface with give address specified!')

    if 'ssh_client' in options:
        config = options['ssh_client']
        if 'source_address' in config:
            if not is_addr_assigned(config['source_address']):
                raise ConfigError('No interface with give address specified!')

    return None

def generate(options):
    render(curlrc_config, 'system/curlrc.tmpl', options, trim_blocks=True)
    render(ssh_config, 'system/ssh_config.tmpl', options, trim_blocks=True)
    return None

def apply(options):
    # Beep action
    if 'beep_if_fully_booted' in options.keys():
        call('systemctl enable vyos-beep.service')
    else:
        call('systemctl disable vyos-beep.service')

    # Ctrl-Alt-Delete action
    if os.path.exists(systemd_action_file):
        os.unlink(systemd_action_file)

    if 'ctrl_alt_del_action' in options:
        if options['ctrl_alt_del_action'] == 'reboot':
            os.symlink('/lib/systemd/system/reboot.target', systemd_action_file)
        elif options['ctrl_alt_del_action'] == 'poweroff':
            os.symlink('/lib/systemd/system/poweroff.target', systemd_action_file)

    if 'http_client' not in options:
        if os.path.exists(curlrc_config):
            os.unlink(curlrc_config)

    if 'ssh_client' not in options:
        if os.path.exists(ssh_config):
            os.unlink(ssh_config)

    # Reboot system on kernel panic
    with open('/proc/sys/kernel/panic', 'w') as f:
        if 'reboot_on_panic' in options.keys():
            f.write('60')
        else:
            f.write('0')

    if 'keyboard_layout' in options.keys():
        if call('loadkeys {}'.format(options['keyboard_layout'])) != 0:
            raise ConfigError('Does not possible to set keyboard layout: {}'.format(options['keyboard_layout']))
    else:
        call('loadkeys us')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)

