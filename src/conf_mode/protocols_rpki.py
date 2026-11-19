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
from vyos.frrender import get_frrender_dict
from vyos.pki import wrap_openssh_public_key
from vyos.pki import wrap_openssh_private_key
from vyos.utils.dict import dict_search
from vyos.utils.dict import dict_search_args
from vyos.utils.file import write_file
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

def rpki_instances(config_dict):
    instances = {None: config_dict.get('rpki', {})}
    for vrf, vrf_config in (dict_search('vrf.name', config_dict) or {}).items():
        instances[vrf] = dict_search('protocols.rpki', vrf_config) or {}
    return instances

def verify(config_dict):
    # SSH keys of all RPKI instances are written, not only of the one committed
    for vrf, instance in rpki_instances(config_dict).items():
        for peer, peer_config in instance.get('cache', {}).items():
            if 'ssh' not in peer_config:
                continue

            cache = f'RPKI cache "{peer}"' + (f' in VRF "{vrf}"' if vrf else '')
            if 'username' not in peer_config['ssh']:
                raise ConfigError(f'{cache} SSH requires username to be defined!')

            if 'key' not in peer_config['ssh']:
                raise ConfigError(f'{cache} SSH requires key to be defined!')

            key_name = peer_config['ssh']['key']
            key = dict_search_args(instance, 'pki', 'openssh', key_name)
            if not key:
                raise ConfigError(f'{cache} SSH key "{key_name}" not found on PKI subsystem!')

            if not dict_search('public.key', key) or not dict_search('private.key', key):
                raise ConfigError(
                    f'{cache} SSH key "{key_name}" requires public and private key!'
                )

    if not has_frr_protocol_in_dict(config_dict, 'rpki'):
        return None

    vrf = None
    if 'vrf_context' in config_dict:
        vrf = config_dict['vrf_context']

    # equivalent of the C foo ? 'a' : 'b' statement
    rpki = vrf and dict_search(f'vrf.name.{vrf}.protocols.rpki',
                                 config_dict) or config_dict['rpki']

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

    return None

def generate(config_dict):
    for key in glob(f'{rpki_ssh_key_base}*'):
        os.unlink(key)

    # Write keys of all RPKI instances, PKI key changes call this script
    # without a VRF context
    for rpki in rpki_instances(config_dict).values():
        for cache_config in rpki.get('cache', {}).values():
            if 'ssh' in cache_config:
                key_name = cache_config['ssh']['key']
                public_key_data = dict_search_args(rpki, 'pki', 'openssh', key_name, 'public', 'key')
                public_key_type = dict_search_args(rpki, 'pki', 'openssh', key_name, 'public', 'type')
                private_key_data = dict_search_args(rpki, 'pki', 'openssh', key_name, 'private', 'key')

                write_file(cache_config['ssh']['public_key_file'], wrap_openssh_public_key(public_key_data, public_key_type))
                write_file(cache_config['ssh']['private_key_file'], wrap_openssh_private_key(private_key_data))

    return None

def apply(config_dict):
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
