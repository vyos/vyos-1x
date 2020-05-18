#!/usr/bin/env python3
#
# Copyright (C) 2018-2019 VyOS maintainers and contributors
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

from stat import S_IRUSR, S_IWUSR, S_IRGRP
from sys import exit

from vyos.config import Config
from vyos import ConfigError
from vyos.command import call
from vyos.template import render


config_file = r'/etc/radvd.conf'

default_config_data = {
    'interfaces': []
}

def get_config():
    rtradv = default_config_data
    conf = Config()
    base_level = ['service', 'router-advert']

    if not conf.exists(base_level):
        return rtradv

    for interface in conf.list_nodes(base_level + ['interface']):
        intf = {
            'name': interface,
            'hop_limit' : '64',
            'default_lifetime': '',
            'default_preference': 'medium',
            'dnssl': [],
            'link_mtu': '',
            'managed_flag': 'off',
            'interval_max': '600',
            'interval_min': '',
            'name_server': [],
            'other_config_flag': 'off',
            'prefixes' : [],
            'reachable_time': '0',
            'retrans_timer': '0',
            'send_advert': 'on'
        }

        # set config level first to reduce boilerplate code
        conf.set_level(base_level + ['interface', interface])

        if conf.exists(['hop-limit']):
            intf['hop_limit'] = conf.return_value(['hop-limit'])

        if conf.exists(['default-lifetim']):
            intf['default_lifetime'] = conf.return_value(['default-lifetim'])

        if conf.exists(['default-preference']):
            intf['default_preference'] = conf.return_value(['default-preference'])

        if conf.exists(['dnssl']):
            intf['dnssl'] = conf.return_values(['dnssl'])

        if conf.exists(['link-mtu']):
            intf['link_mtu'] = conf.return_value(['link-mtu'])

        if conf.exists(['managed-flag']):
            intf['managed_flag'] = 'on'

        if conf.exists(['interval', 'max']):
            intf['interval_max'] = conf.return_value(['interval', 'max'])

        if conf.exists(['interval', 'min']):
            intf['interval_min'] = conf.return_value(['interval', 'min'])

        if conf.exists(['name-server']):
            intf['name_server'] = conf.return_values(['name-server'])

        if conf.exists(['other-config-flag']):
            intf['other_config_flag'] = 'on'

        if conf.exists(['reachable-time']):
            intf['reachable_time'] = conf.return_value(['reachable-time'])

        if conf.exists(['retrans-timer']):
            intf['retrans_timer'] = conf.return_value(['retrans-timer'])

        if conf.exists(['no-send-advert']):
            intf['send_advert'] = 'off'

        for prefix in conf.list_nodes(['prefix']):
            tmp = {
                'prefix' : prefix,
                'autonomous_flag' : 'on',
                'on_link' : 'on',
                'preferred_lifetime': '14400',
                'valid_lifetime' : '2592000'

            }

            # set config level first to reduce boilerplate code
            conf.set_level(base_level + ['interface', interface, 'prefix', prefix])

            if conf.exists(['no-autonomous-flag']):
                tmp['autonomous_flag'] = 'off'

            if conf.exists(['no-on-link-flag']):
                tmp['on_link'] = 'off'

            if conf.exists(['preferred-lifetime']):
                tmp['preferred_lifetime'] = conf.return_value(['preferred-lifetime'])

            if conf.exists(['valid-lifetime']):
                tmp['valid_lifetime'] = conf.return_value(['valid-lifetime'])

            intf['prefixes'].append(tmp)

        rtradv['interfaces'].append(intf)

    return rtradv

def verify(rtradv):
    return None

def generate(rtradv):
    if not rtradv['interfaces']:
        return None

    render(config_file, 'router-advert/radvd.conf.tmpl', rtradv, trim_blocks=True)

    # adjust file permissions of new configuration file
    if os.path.exists(config_file):
        os.chmod(config_file, S_IRUSR | S_IWUSR | S_IRGRP)

    return None

def apply(rtradv):
    if not rtradv['interfaces']:
        # bail out early - looks like removal from running config
        call('systemctl stop radvd.service')
        if os.path.exists(config_file):
            os.unlink(config_file)

        return None

    call('systemctl restart radvd.service')
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
