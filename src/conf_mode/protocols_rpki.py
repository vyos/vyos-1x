#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

from glob import glob
from sys import exit
from sys import argv

from vyos.config import Config
from vyos.configverify import has_frr_protocol_in_dict
from vyos.frrender import FRRender
from vyos.frrender import get_frrender_dict
from vyos.pki import wrap_openssh_public_key
from vyos.pki import wrap_openssh_private_key
from vyos.utils.dict import dict_search_args
from vyos.utils.file import write_file
from vyos.utils.process import is_systemd_service_running
from vyos import ConfigError
from vyos import airbag
airbag.enable()

rpki_ssh_key_base = '/run/frr/id_rpki'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    return get_frrender_dict(conf, argv)

def verify(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'rpki'):
        return None

    vrf = None
    if 'vrf_context' in config_dict:
        vrf = config_dict['vrf_context']

    # eqivalent of the C foo ? 'a' : 'b' statement
    rpki = vrf and config_dict['vrf']['name'][vrf]['protocols']['rpki'] or config_dict['rpki']

    if 'cache' in rpki:
        preferences = []
        for peer, peer_config in rpki['cache'].items():
            for mandatory in ['port', 'preference']:
                if mandatory not in peer_config:
                    raise ConfigError(f'RPKI cache "{peer}" {mandatory} must be defined!')

            if 'preference' in peer_config:
                preference = peer_config['preference']
                if preference in preferences:
                    raise ConfigError(f'RPKI cache with preference {preference} already configured!')
                preferences.append(preference)

            if 'ssh' in peer_config:
                if 'username' not in peer_config['ssh']:
                    raise ConfigError('RPKI+SSH requires username to be defined!')

                if 'key' not in peer_config['ssh'] or 'openssh' not in rpki['pki']:
                    raise ConfigError('RPKI+SSH requires key to be defined!')

                if peer_config['ssh']['key'] not in rpki['pki']['openssh']:
                    raise ConfigError('RPKI+SSH key not found on PKI subsystem!')

    return None

def generate(config_dict):
    for key in glob(f'{rpki_ssh_key_base}*'):
        os.unlink(key)

    if not has_frr_protocol_in_dict(config_dict, 'rpki'):
        return None

    vrf = None
    if 'vrf_context' in config_dict:
        vrf = config_dict['vrf_context']

    # eqivalent of the C foo ? 'a' : 'b' statement
    rpki = vrf and config_dict['vrf']['name'][vrf]['protocols']['rpki'] or config_dict['rpki']

    if 'cache' in rpki:
        for cache, cache_config in rpki['cache'].items():
            if 'ssh' in cache_config:
                key_name = cache_config['ssh']['key']
                public_key_data = dict_search_args(rpki['pki'], 'openssh', key_name, 'public', 'key')
                public_key_type = dict_search_args(rpki['pki'], 'openssh', key_name, 'public', 'type')
                private_key_data = dict_search_args(rpki['pki'], 'openssh', key_name, 'private', 'key')

                cache_config['ssh']['public_key_file'] = f'{rpki_ssh_key_base}_{cache}.pub'
                cache_config['ssh']['private_key_file'] = f'{rpki_ssh_key_base}_{cache}'

                write_file(cache_config['ssh']['public_key_file'], wrap_openssh_public_key(public_key_data, public_key_type))
                write_file(cache_config['ssh']['private_key_file'], wrap_openssh_private_key(private_key_data))

    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().generate(config_dict)
    return None

def apply(config_dict):
    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().apply()
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
