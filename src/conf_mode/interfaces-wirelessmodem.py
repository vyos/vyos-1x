#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

from fnmatch import fnmatch
from sys import exit

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configverify import verify_vrf
from vyos.template import render
from vyos.util import call
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def check_kmod():
    modules = ['option', 'usb_wwan', 'usbserial']
    for module in modules:
        if not os.path.exists(f'/sys/module/{module}'):
            if call(f'modprobe {module}') != 0:
                raise ConfigError(f'Loading Kernel module {module} failed')

def find_device_file(device):
    """ Recurively search /dev for the given device file and return its full path.
        If no device file was found 'None' is returned """
    for root, dirs, files in os.walk('/dev'):
        for basename in files:
            if fnmatch(basename, device):
                return os.path.join(root, basename)

    return None

def get_config():
    """ Retrive CLI config as dictionary. Dictionary can never be empty,
    as at least the interface name will be added or a deleted flag """
    conf = Config()

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    # retrieve interface default values
    base = ['interfaces', 'wirelessmodem']
    default_values = defaults(base)

    ifname = os.environ['VYOS_TAGNODE_VALUE']
    base = base + [ifname]

    wwan = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    # Check if interface has been removed
    if wwan == {}:
        wwan.update({'deleted' : ''})

    # We have gathered the dict representation of the CLI, but there are
    # default options which we need to update into the dictionary
    # retrived.
    wwan = dict_merge(default_values, wwan)

    # Add interface instance name into dictionary
    wwan.update({'ifname': ifname})

    return wwan

def verify(wwan):
    if 'deleted' in wwan.keys():
        return None

    if not 'apn' in wwan.keys():
        raise ConfigError('No APN configured for "{ifname}"'.format(**wwan))

    if not 'device' in wwan.keys():
        raise ConfigError('Physical "device" must be configured')

    # we can not use isfile() here as Linux device files are no regular files
    # thus the check will return False
    if not os.path.exists(find_device_file(wwan['device'])):
        raise ConfigError('Device "{device}" does not exist'.format(**wwan))

    verify_vrf(wwan)

    return None

def generate(wwan):
    # set up configuration file path variables where our templates will be
    # rendered into
    ifname = wwan['ifname']
    config_wwan = f'/etc/ppp/peers/{ifname}'
    config_wwan_chat = f'/etc/ppp/peers/chat.{ifname}'
    script_wwan_pre_up = f'/etc/ppp/ip-pre-up.d/1010-vyos-wwan-{ifname}'
    script_wwan_ip_up = f'/etc/ppp/ip-up.d/1010-vyos-wwan-{ifname}'
    script_wwan_ip_down = f'/etc/ppp/ip-down.d/1010-vyos-wwan-{ifname}'

    config_files = [config_wwan, config_wwan_chat, script_wwan_pre_up,
                    script_wwan_ip_up, script_wwan_ip_down]

    # Always hang-up WWAN connection prior generating new configuration file
    call(f'systemctl stop ppp@{ifname}.service')

    if 'deleted' in wwan:
        # Delete PPP configuration files
        for file in config_files:
            if os.path.exists(file):
                os.unlink(file)

    else:
        wwan['device'] = find_device_file(wwan['device'])

        # Create PPP configuration files
        render(config_wwan, 'wwan/peer.tmpl', wwan)
        # Create PPP chat script
        render(config_wwan_chat, 'wwan/chat.tmpl', wwan)

        # generated script file must be executable

        # Create script for ip-pre-up.d
        render(script_wwan_pre_up, 'wwan/ip-pre-up.script.tmpl',
               wwan, permission=0o755)
        # Create script for ip-up.d
        render(script_wwan_ip_up, 'wwan/ip-up.script.tmpl',
               wwan, permission=0o755)
        # Create script for ip-down.d
        render(script_wwan_ip_down, 'wwan/ip-down.script.tmpl',
               wwan, permission=0o755)

    return None

def apply(wwan):
    if 'deleted' in wwan.keys():
        # bail out early
        return None

    if not 'disable' in wwan.keys():
        # "dial" WWAN connection
        call('systemctl start ppp@{ifname}.service'.format(**wwan))

    return None

if __name__ == '__main__':
    try:
        check_kmod()
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
