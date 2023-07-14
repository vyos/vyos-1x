#!/usr/bin/env python3
#
# Copyright (C) 2019-2022 VyOS maintainers and contributors
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
from time import sleep

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configverify import verify_source_interface
from vyos.template import render
from vyos.utils.process import cmd
from vyos.util import is_systemd_service_running
from vyos.validate import is_addr_assigned
from vyos.validate import is_intf_addr_assigned
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

curlrc_config = r'/etc/curlrc'
ssh_config = r'/etc/ssh/ssh_config.d/91-vyos-ssh-client-options.conf'
systemd_action_file = '/lib/systemd/system/ctrl-alt-del.target'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'option']
    options = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)
    options = dict_merge(default_values, options)

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
            address = config['source_address']
            if not is_addr_assigned(config['source_address']):
                raise ConfigError('No interface with address "{address}" configured!')

        if 'source_interface' in config:
            verify_source_interface(config)
            if 'source_address' in config:
                address = config['source_address']
                interface = config['source_interface']
                if not is_intf_addr_assigned(interface, address):
                    raise ConfigError(f'Address "{address}" not assigned on interface "{interface}"!')

    return None

def generate(options):
    render(curlrc_config, 'system/curlrc.j2', options)
    render(ssh_config, 'system/ssh_config.j2', options)
    return None

def apply(options):
    # System bootup beep
    if 'startup_beep' in options:
        cmd('systemctl enable vyos-beep.service')
    else:
        cmd('systemctl disable vyos-beep.service')

    # Ctrl-Alt-Delete action
    if os.path.exists(systemd_action_file):
        os.unlink(systemd_action_file)
    if 'ctrl_alt_delete' in options:
        if options['ctrl_alt_delete'] == 'reboot':
            os.symlink('/lib/systemd/system/reboot.target', systemd_action_file)
        elif options['ctrl_alt_delete'] == 'poweroff':
            os.symlink('/lib/systemd/system/poweroff.target', systemd_action_file)

    # Configure HTTP client
    if 'http_client' not in options:
        if os.path.exists(curlrc_config):
            os.unlink(curlrc_config)

    # Configure SSH client
    if 'ssh_client' not in options:
        if os.path.exists(ssh_config):
            os.unlink(ssh_config)

    # Reboot system on kernel panic
    timeout = '0'
    if 'reboot_on_panic' in options:
        timeout = '60'
    with open('/proc/sys/kernel/panic', 'w') as f:
        f.write(timeout)

    # tuned - performance tuning
    if 'performance' in options:
        cmd('systemctl restart tuned.service')
        # wait until daemon has started before sending configuration
        while (not is_systemd_service_running('tuned.service')):
            sleep(0.250)
        cmd('tuned-adm profile network-{performance}'.format(**options))
    else:
        cmd('systemctl stop tuned.service')

    # Keyboard layout - there will be always the default key inside the dict
    # but we check for key existence anyway
    if 'keyboard_layout' in options:
        cmd('loadkeys {keyboard_layout}'.format(**options))

    # Enable/diable root-partition-auto-resize SystemD service
    if 'root_partition_auto_resize' in options:
      cmd('systemctl enable root-partition-auto-resize.service')
    else:
      cmd('systemctl disable root-partition-auto-resize.service')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
