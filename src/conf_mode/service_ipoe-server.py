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
import re

from copy import deepcopy
from stat import S_IRUSR, S_IWUSR, S_IRGRP
from sys import exit

from vyos.config import Config
from vyos.template import render
from vyos.util import call, get_half_cpus
from vyos.validate import is_ipv4
from vyos import ConfigError

from vyos import airbag
airbag.enable()

ipoe_conf = '/run/accel-pppd/ipoe.conf'
ipoe_chap_secrets = '/run/accel-pppd/ipoe.chap-secrets'

default_config_data = {
    'auth_mode': 'local',
    'auth_interfaces': [],
    'chap_secrets_file': ipoe_chap_secrets, # used in Jinja2 template
    'interfaces': [],
    'dnsv4': [],
    'dnsv6': [],
    'client_ipv6_pool': [],
    'client_ipv6_delegate_prefix': [],
    'radius_server': [],
    'radius_acct_tmo': '3',
    'radius_max_try': '3',
    'radius_timeout': '3',
    'radius_nas_id': '',
    'radius_nas_ip': '',
    'radius_source_address': '',
    'radius_shaper_attr': '',
    'radius_shaper_vendor': '',
    'radius_dynamic_author': '',
    'thread_cnt': get_half_cpus()
}

def get_config():
    conf = Config()
    base_path = ['service', 'ipoe-server']
    if not conf.exists(base_path):
        return None

    conf.set_level(base_path)
    ipoe = deepcopy(default_config_data)

    for interface in conf.list_nodes(['interface']):
        tmp  = {
            'mode': 'L2',
            'name': interface,
            'shared': '1',
            # may need a config option, can be dhcpv4 or up for unclassified pkts
            'sess_start': 'dhcpv4',
            'range': None,
            'ifcfg': '1',
            'vlan_mon': []
        }

        conf.set_level(base_path + ['interface', interface])

        if conf.exists(['network-mode']):
            tmp['mode'] = conf.return_value(['network-mode'])

        if conf.exists(['network']):
            mode = conf.return_value(['network'])
            if mode == 'vlan':
                tmp['shared'] = '0'

                if conf.exists(['vlan-id']):
                    tmp['vlan_mon'] += conf.return_values(['vlan-id'])

                if conf.exists(['vlan-range']):
                    tmp['vlan_mon'] += conf.return_values(['vlan-range'])

        if conf.exists(['client-subnet']):
            tmp['range'] = conf.return_value(['client-subnet'])

        ipoe['interfaces'].append(tmp)

    conf.set_level(base_path)

    if conf.exists(['name-server']):
        for name_server in conf.return_values(['name-server']):
            if is_ipv4(name_server):
                ipoe['dnsv4'].append(name_server)
            else:
                ipoe['dnsv6'].append(name_server)

    if conf.exists(['authentication', 'mode']):
        ipoe['auth_mode'] = conf.return_value(['authentication', 'mode'])

    if conf.exists(['authentication', 'interface']):
        for interface in conf.list_nodes(['authentication', 'interface']):
            tmp = {
                'name': interface,
                'mac': []
            }
            for mac in conf.list_nodes(['authentication', 'interface', interface, 'mac-address']):
                client = {
                    'address': mac,
                    'rate_download': '',
                    'rate_upload': '',
                    'vlan_id': ''
                }
                conf.set_level(base_path + ['authentication', 'interface', interface, 'mac-address', mac])

                if conf.exists(['rate-limit', 'download']):
                    client['rate_download'] = conf.return_value(['rate-limit', 'download'])

                if conf.exists(['rate-limit', 'upload']):
                    client['rate_upload'] = conf.return_value(['rate-limit', 'upload'])

                if conf.exists(['vlan-id']):
                    client['vlan'] = conf.return_value(['vlan-id'])

                tmp['mac'].append(client)

            ipoe['auth_interfaces'].append(tmp)

    conf.set_level(base_path)

    #
    # authentication mode radius servers and settings
    if conf.exists(['authentication', 'mode', 'radius']):
        for server in conf.list_nodes(['authentication', 'radius', 'server']):
            radius = {
                'server' : server,
                'key' : '',
                'fail_time' : 0,
                'port' : '1812'
            }

            conf.set_level(base_path + ['authentication', 'radius', 'server', server])

            if conf.exists(['fail-time']):
                radius['fail_time'] = conf.return_value(['fail-time'])

            if conf.exists(['port']):
                radius['port'] = conf.return_value(['port'])

            if conf.exists(['key']):
                radius['key'] = conf.return_value(['key'])

            if not conf.exists(['disable']):
                ipoe['radius_server'].append(radius)

    #
    # advanced radius-setting
    conf.set_level(base_path + ['authentication', 'radius'])
    if conf.exists(['acct-timeout']):
        ipoe['radius_acct_tmo'] = conf.return_value(['acct-timeout'])

    if conf.exists(['max-try']):
        ipoe['radius_max_try'] = conf.return_value(['max-try'])

    if conf.exists(['timeout']):
        ipoe['radius_timeout'] = conf.return_value(['timeout'])

    if conf.exists(['nas-identifier']):
        ipoe['radius_nas_id'] = conf.return_value(['nas-identifier'])

    if conf.exists(['nas-ip-address']):
        ipoe['radius_nas_ip'] = conf.return_value(['nas-ip-address'])

    if conf.exists(['source-address']):
        ipoe['radius_source_address'] = conf.return_value(['source-address'])

    # Dynamic Authorization Extensions (DOA)/Change Of Authentication (COA)
    if conf.exists(['dynamic-author']):
        dae = {
            'port' : '',
            'server' : '',
            'key' : ''
        }

        if conf.exists(['dynamic-author', 'server']):
            dae['server'] = conf.return_value(['dynamic-author', 'server'])

        if conf.exists(['dynamic-author', 'port']):
            dae['port'] = conf.return_value(['dynamic-author', 'port'])

        if conf.exists(['dynamic-author', 'key']):
            dae['key'] = conf.return_value(['dynamic-author', 'key'])

        ipoe['radius_dynamic_author'] = dae


    conf.set_level(base_path)
    if conf.exists(['client-ipv6-pool', 'prefix']):
        for prefix in conf.list_nodes(['client-ipv6-pool', 'prefix']):
            tmp = {
                'prefix': prefix,
                'mask': '64'
            }

            if conf.exists(['client-ipv6-pool', 'prefix', prefix, 'mask']):
                tmp['mask'] = conf.return_value(['client-ipv6-pool', 'prefix', prefix, 'mask'])

            ipoe['client_ipv6_pool'].append(tmp)


    if conf.exists(['client-ipv6-pool', 'delegate']):
        for prefix in conf.list_nodes(['client-ipv6-pool', 'delegate']):
            tmp = {
                'prefix': prefix,
                'mask': ''
            }

            if conf.exists(['client-ipv6-pool', 'delegate', prefix, 'delegation-prefix']):
                tmp['mask'] = conf.return_value(['client-ipv6-pool', 'delegate', prefix, 'delegation-prefix'])

            ipoe['client_ipv6_delegate_prefix'].append(tmp)

    return ipoe


def verify(ipoe):
    if not ipoe:
        return None

    if not ipoe['interfaces']:
        raise ConfigError('No IPoE interface configured')

    for interface in ipoe['interfaces']:
        if not interface['range']:
            raise ConfigError(f'No IPoE client subnet defined on interface "{ interface }"')

    if len(ipoe['dnsv4']) > 2:
        raise ConfigError('Not more then two IPv4 DNS name-servers can be configured')

    if len(ipoe['dnsv6']) > 3:
        raise ConfigError('Not more then three IPv6 DNS name-servers can be configured')

    if ipoe['auth_mode'] == 'radius':
        if len(ipoe['radius_server']) == 0:
            raise ConfigError('RADIUS authentication requires at least one server')

        for radius in ipoe['radius_server']:
            if not radius['key']:
                server = radius['server']
                raise ConfigError(f'Missing RADIUS secret key for server "{ server }"')

    if ipoe['client_ipv6_delegate_prefix'] and not ipoe['client_ipv6_pool']:
        raise ConfigError('IPoE IPv6 deletate-prefix requires IPv6 prefix to be configured!')

    return None


def generate(ipoe):
    if not ipoe:
        return None

    render(ipoe_conf, 'accel-ppp/ipoe.config.tmpl', ipoe, trim_blocks=True)

    if ipoe['auth_mode'] == 'local':
        render(ipoe_chap_secrets, 'accel-ppp/chap-secrets.ipoe.tmpl', ipoe)
        os.chmod(ipoe_chap_secrets, S_IRUSR | S_IWUSR | S_IRGRP)

    else:
        if os.path.exists(ipoe_chap_secrets):
             os.unlink(ipoe_chap_secrets)

    return None


def apply(ipoe):
    if ipoe == None:
        call('systemctl stop accel-ppp@ipoe.service')
        for file in [ipoe_conf, ipoe_chap_secrets]:
            if os.path.exists(file):
                os.unlink(file)

        return None

    call('systemctl restart accel-ppp@ipoe.service')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
