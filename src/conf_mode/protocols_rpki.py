#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
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

from vyos.config import Config
from vyos.pki import wrap_openssh_public_key
from vyos.pki import wrap_openssh_private_key
from vyos.template import render_to_string
from vyos.utils.dict import dict_search_args
from vyos.utils.file import write_file
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

rpki_ssh_key_base = '/run/frr/id_rpki'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['protocols', 'rpki']

    rpki = conf.get_config_dict(base, key_mangling=('-', '_'),
                                get_first_key=True, with_pki=True)
    # Bail out early if configuration tree does not exist
    if not conf.exists(base):
        rpki.update({'deleted' : ''})
        return rpki

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    rpki = conf.merge_defaults(rpki, recursive=True)

    return rpki

def verify(rpki):
    if not rpki:
        return None

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

def generate(rpki):
    for key in glob(f'{rpki_ssh_key_base}*'):
        os.unlink(key)

    if not rpki:
        return

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

    rpki['new_frr_config'] = render_to_string('frr/rpki.frr.j2', rpki)

    return None

def apply(rpki):
    bgp_daemon = 'bgpd'

    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()
    frr_cfg.load_configuration(bgp_daemon)
    frr_cfg.modify_section('^rpki', stop_pattern='^exit', remove_stop_mark=True)
    if 'new_frr_config' in rpki:
        frr_cfg.add_before(frr.default_add_before, rpki['new_frr_config'])

    frr_cfg.commit_configuration(bgp_daemon)
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
