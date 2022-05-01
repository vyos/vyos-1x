#!/usr/bin/env python3
#
# Copyright (C) 2017-2022 VyOS maintainers and contributors
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

from vyos.base import Warning
from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.validate import is_addr_assigned
from vyos.validate import is_loopback_addr
from vyos.version import get_version_data
from vyos.util import call
from vyos.util import dict_search
from vyos.xml import defaults
from vyos.template import render
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = "/etc/default/lldpd"
vyos_config_file = "/etc/lldpd.d/01-vyos.conf"
base = ['service', 'lldp']

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    if not conf.exists(base):
        return {}

    lldp = conf.get_config_dict(base, key_mangling=('-', '_'),
                                get_first_key=True, no_tag_node_value_mangle=True)

    if conf.exists(['service', 'snmp']):
        lldp['system_snmp_enabled'] = ''

    version_data = get_version_data()
    lldp['version'] = version_data['version']

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    # location coordinates have a default value
    if 'interface' in lldp:
        for interface, interface_config in lldp['interface'].items():
            default_values = defaults(base + ['interface'])
            if dict_search('location.coordinate_based', interface_config) == None:
                # no location specified - no need to add defaults
                del default_values['location']['coordinate_based']['datum']
                del default_values['location']['coordinate_based']['altitude']

            # cleanup default_values dictionary from inner to outer
            # this might feel overkill here, but it does support easy extension
            # in the future with additional default values
            if len(default_values['location']['coordinate_based']) == 0:
                del default_values['location']['coordinate_based']
            if len(default_values['location']) == 0:
                del default_values['location']

            lldp['interface'][interface] = dict_merge(default_values,
                                                   lldp['interface'][interface])

    return lldp

def verify(lldp):
    # bail out early - looks like removal from running config
    if lldp is None:
        return

    if 'management_address' in lldp:
        for address in lldp['management_address']:
            message = f'LLDP management address "{address}" is invalid'
            if is_loopback_addr(address):
                Warning(f'{message} - loopback address')
            elif not is_addr_assigned(address):
                Warning(f'{message} - not assigned to any interface')

    if 'interface' in lldp:
        for interface, interface_config in lldp['interface'].items():
            # bail out early if no location info present in interface config
            if 'location' not in interface_config:
                continue
            if 'coordinate_based' in interface_config['location']:
                if not {'latitude', 'latitude'} <= set(interface_config['location']['coordinate_based']):
                    raise ConfigError(f'Must define both longitude and latitude for "{interface}" location!')

    # check options
    if 'snmp' in lldp and 'enable' in lldp['snmp']:
        if 'system_snmp_enabled' not in lldp:
            raise ConfigError('SNMP must be configured to enable LLDP SNMP')


def generate(lldp):
    # bail out early - looks like removal from running config
    if lldp is None:
        return

    render(config_file, 'lldp/lldpd.j2', lldp)
    render(vyos_config_file, 'lldp/vyos.conf.j2', lldp)

def apply(lldp):
    systemd_service = 'lldpd.service'
    if lldp:
        # start/restart lldp service
        call(f'systemctl restart {systemd_service}')
    else:
        # LLDP service has been terminated
        call(f'systemctl stop {systemd_service}')
        if os.path.isfile(config_file):
            os.unlink(config_file)
        if os.path.isfile(vyos_config_file):
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

