#!/usr/bin/env python3
#
# Copyright (C) 2017-2020 VyOS maintainers and contributors
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
import re

from copy import deepcopy
from jinja2 import FileSystemLoader, Environment
from sys import exit

from vyos.config import Config
from vyos.validate import is_addr_assigned,is_loopback_addr
from vyos.defaults import directories as vyos_data_dir
from vyos.version import get_version_data
from vyos import ConfigError

config_file = "/etc/default/lldpd"
vyos_config_file = "/etc/lldpd.d/01-vyos.conf"
base = ['service', 'lldp']

default_config_data = {
    "options": '',
    "interface_list": '',
    "location": ''
}

def get_options(config):
    options = {}
    config.set_level(base)

    options['listen_vlan'] = config.exists('listen-vlan')
    options['mgmt_addr'] = []
    for addr in config.return_values('management-address'):
        if is_addr_assigned(addr) and not is_loopback_addr(addr):
            options['mgmt_addr'].append(addr)
        else:
            message = 'WARNING: LLDP management address {0} invalid - '.format(addr)
            if is_loopback_addr(addr):
                message += '(loopback address).'
            else:
                message += 'address not found.'
            print(message)

    snmp = config.exists('snmp enable')
    options["snmp"] = snmp
    if snmp:
        config.set_level('')
        options["sys_snmp"] = config.exists('service snmp')
        config.set_level(base)

    config.set_level(base + ['legacy-protocols'])
    options['cdp'] = config.exists('cdp')
    options['edp'] = config.exists('edp')
    options['fdp'] = config.exists('fdp')
    options['sonmp'] = config.exists('sonmp')

    # start with an unknown version information
    version_data = get_version_data()
    options['description'] = version_data['version']
    options['listen_on'] = []

    return options

def get_interface_list(config):
    config.set_level(base)
    intfs_names = config.list_nodes(['interface'])
    if len(intfs_names) < 0:
        return 0

    interface_list = []
    for name in intfs_names:
        config.set_level(base + ['interface', name])
        disable = config.exists(['disable'])
        intf = {
            'name': name,
            'disable': disable
        }
        interface_list.append(intf)
    return interface_list


def get_location_intf(config, name):
    path = base + ['interface', name]
    config.set_level(path)

    config.set_level(path + ['location'])
    elin = ''
    coordinate_based = {}

    if config.exists('elin'):
        elin = config.return_value('elin')

    if config.exists('coordinate-based'):
        config.set_level(path + ['location', 'coordinate-based'])

        coordinate_based['latitude'] = config.return_value(['latitude'])
        coordinate_based['longitude'] = config.return_value(['longitude'])

        coordinate_based['altitude'] = '0'
        if config.exists(['altitude']):
            coordinate_based['altitude'] = config.return_value(['altitude'])

        coordinate_based['datum'] = 'WGS84'
        if config.exists(['datum']):
            coordinate_based['datum'] = config.return_value(['datum'])

    intf = {
        'name': name,
        'elin': elin,
        'coordinate_based': coordinate_based

    }
    return intf


def get_location(config):
    config.set_level(base)
    intfs_names = config.list_nodes(['interface'])
    if len(intfs_names) < 0:
        return 0

    if config.exists('disable'):
        return 0

    intfs_location = []
    for name in intfs_names:
        intf = get_location_intf(config, name)
        intfs_location.append(intf)

    return intfs_location


def get_config():
    lldp = deepcopy(default_config_data)
    conf = Config()
    if not conf.exists(base):
        return None
    else:
        lldp['options'] = get_options(conf)
        lldp['interface_list'] = get_interface_list(conf)
        lldp['location'] = get_location(conf)

        return lldp


def verify(lldp):
    # bail out early - looks like removal from running config
    if lldp is None:
        return

    # check location
    for location in lldp['location']:
        # check coordinate-based
        if len(location['coordinate_based']) > 0:
            # check longitude and latitude
            if not location['coordinate_based']['longitude']:
                raise ConfigError('Must define longitude for interface {0}'.format(location['name']))

            if not location['coordinate_based']['latitude']:
                raise ConfigError('Must define latitude for interface {0}'.format(location['name']))

            if not re.match(r'^(\d+)(\.\d+)?[nNsS]$', location['coordinate_based']['latitude']):
                raise ConfigError('Invalid location for interface {0}:\n' \
                                  'latitude should be a number followed by S or N'.format(location['name']))

            if not re.match(r'^(\d+)(\.\d+)?[eEwW]$', location['coordinate_based']['longitude']):
                raise ConfigError('Invalid location for interface {0}:\n' \
                                  'longitude should be a number followed by E or W'.format(location['name']))

            # check altitude and datum if exist
            if location['coordinate_based']['altitude']:
                if not re.match(r'^[-+0-9\.]+$', location['coordinate_based']['altitude']):
                    raise ConfigError('Invalid location for interface {0}:\n' \
                                      'altitude should be a positive or negative number'.format(location['name']))

            if location['coordinate_based']['datum']:
                if not re.match(r'^(WGS84|NAD83|MLLW)$', location['coordinate_based']['datum']):
                    raise ConfigError("Invalid location for interface {0}:\n' \
                                      'datum should be WGS84, NAD83, or MLLW".format(location['name']))

        # check elin
        elif location['elin']:
            if not re.match(r'^[0-9]{10,25}$', location['elin']):
                raise ConfigError('Invalid location for interface {0}:\n' \
                                  'ELIN number must be between 10-25 numbers'.format(location['name']))

    # check options
    if lldp['options']['snmp']:
        if not lldp['options']['sys_snmp']:
            raise ConfigError('SNMP must be configured to enable LLDP SNMP')


def generate(lldp):
    # bail out early - looks like removal from running config
    if lldp is None:
        return

    # Prepare Jinja2 template loader from files
    tmpl_path = os.path.join(vyos_data_dir['data'], 'templates', 'lldp')
    fs_loader = FileSystemLoader(tmpl_path)
    env = Environment(loader=fs_loader)

    # generate listen on interfaces
    for intf in lldp['interface_list']:
        tmp = ''
        # add exclamation mark if interface is disabled
        if intf['disable']:
            tmp = '!'

        tmp += intf['name']
        lldp['options']['listen_on'].append(tmp)

    # generate /etc/default/lldpd
    tmpl = env.get_template('lldpd.tmpl')
    config_text = tmpl.render(lldp)
    with open(config_file, 'w') as f:
        f.write(config_text)

    # generate /etc/lldpd.d/01-vyos.conf
    tmpl = env.get_template('vyos.conf.tmpl')
    config_text = tmpl.render(lldp)
    with open(vyos_config_file, 'w') as f:
        f.write(config_text)


def apply(lldp):
    if lldp:
        # start/restart lldp service
        os.system('sudo systemctl restart lldpd.service')
    else:
        # LLDP service has been terminated
        os.system('sudo systemctl stop lldpd.service')
        os.unlink(config_file)
        os.unlink(vyos_config_file)

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)

