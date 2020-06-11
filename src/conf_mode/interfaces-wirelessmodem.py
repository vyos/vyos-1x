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

from copy import deepcopy
from fnmatch import fnmatch
from netifaces import interfaces
from sys import exit

from vyos.config import Config
from vyos.ifconfig import BridgeIf, Section
from vyos.template import render
from vyos.util import call
from vyos.validate import is_member
from vyos import ConfigError

from vyos import airbag
airbag.enable()

default_config_data = {
    'apn': '',
    'chat_script': '',
    'deleted': False,
    'description': '',
    'device': '',
    'disable': False,
    'disable_link_detect': 1,
    'on_demand': False,
    'metric': '10',
    'mtu': '1500',
    'name_server': True,
    'is_bridge_member': False,
    'intf': '',
    'vrf': ''
}

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
    wwan = deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    wwan['intf'] = os.environ['VYOS_TAGNODE_VALUE']
    wwan['chat_script'] = f"/etc/ppp/peers/chat.{wwan['intf']}"

    # Check if interface has been removed
    if not conf.exists('interfaces wirelessmodem ' + wwan['intf']):
        wwan['deleted'] = True
        return wwan

    # set new configuration level
    conf.set_level('interfaces wirelessmodem ' + wwan['intf'])

    # get metrick for backup default route
    if conf.exists(['apn']):
        wwan['apn'] = conf.return_value(['apn'])

    # get metrick for backup default route
    if conf.exists(['backup', 'distance']):
        wwan['metric'] = conf.return_value(['backup', 'distance'])

    # Retrieve interface description
    if conf.exists(['description']):
        wwan['description'] = conf.return_value(['description'])

    # System device name
    if conf.exists(['device']):
        tmp = conf.return_value(['device'])
        wwan['device'] = find_device_file(tmp)
        # If device file was not found in /dev we will just re-use
        # the plain device name, thus we can trigger the exception
        # in verify() as it's a non existent file
        if wwan['device'] == None:
            wwan['device'] = tmp

    # disable interface
    if conf.exists('disable'):
        wwan['disable'] = True

    # ignore link state changes
    if conf.exists('disable-link-detect'):
        wwan['disable_link_detect'] = 2

    # Do not use DNS servers provided by the peer
    if conf.exists(['mtu']):
        wwan['mtu'] = conf.return_value(['mtu'])

    # Do not use DNS servers provided by the peer
    if conf.exists(['no-peer-dns']):
        wwan['name_server'] = False

    # Access concentrator name (only connect to this concentrator)
    if conf.exists(['ondemand']):
        wwan['on_demand'] = True

    # retrieve VRF instance
    if conf.exists('vrf'):
        wwan['vrf'] = conf.return_value(['vrf'])

    return wwan

def verify(wwan):
    if wwan['deleted']:
        return None

    if not wwan['apn']:
        raise ConfigError('No APN configured for "{intf}"'.format(**wwan))

    if not wwan['device']:
        raise ConfigError('Physical "device" must be configured')

    # we can not use isfile() here as Linux device files are no regular files
    # thus the check will return False
    if not os.path.exists('{device}'.format(**wwan)):
        raise ConfigError('Device "{device}" does not exist'.format(**wwan))

    if wwan['vrf'] and wwan['vrf'] not in interfaces():
        raise ConfigError('VRF "{vrf}" does not exist'.format(**wwan))

    return None

def generate(wwan):
    # set up configuration file path variables where our templates will be
    # rendered into
    intf = wwan['intf']
    config_wwan = f'/etc/ppp/peers/{intf}'
    config_wwan_chat = wwan['chat_script']
    script_wwan_pre_up = f'/etc/ppp/ip-pre-up.d/1010-vyos-wwan-{intf}'
    script_wwan_ip_up = f'/etc/ppp/ip-up.d/1010-vyos-wwan-{intf}'
    script_wwan_ip_down = f'/etc/ppp/ip-down.d/1010-vyos-wwan-{intf}'

    config_files = [config_wwan, config_wwan_chat, script_wwan_pre_up,
                    script_wwan_ip_up, script_wwan_ip_down]

    # Always hang-up WWAN connection prior generating new configuration file
    call(f'systemctl stop ppp@{intf}.service')

    if wwan['deleted']:
        # Delete PPP configuration files
        for file in config_files:
            if os.path.exists(file):
                os.unlink(file)

    else:
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
    if wwan['deleted']:
        # bail out early
        return None

    if not wwan['disable']:
        # "dial" WWAN connection
        intf = wwan['intf']
        call(f'systemctl start ppp@{intf}.service')

        # re-add ourselves to any bridge we might have fallen out of
        # FIXME: wwan isn't under vyos.ifconfig so we can't call
        # Interfaces.add_to_bridge() so STP settings won't get applied
        if wwan['is_bridge_member'] in Section.interfaces('bridge'):
            BridgeIf(wwan['is_bridge_member'], create=False).add_port(wwan['intf'])

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
