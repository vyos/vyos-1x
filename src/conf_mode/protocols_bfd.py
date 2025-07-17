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

from vyos.config import Config
from vyos.configverify import verify_vrf
from vyos.configverify import has_frr_protocol_in_dict
from vyos.frrender import FRRender
from vyos.frrender import get_frrender_dict
from vyos.template import is_ipv6
from vyos.utils.network import is_ipv6_link_local
from vyos.utils.process import is_systemd_service_running
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    return get_frrender_dict(conf)

def verify(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'bfd'):
        return None

    bfd = config_dict['bfd']
    if 'peer' in bfd:
        for peer, peer_config in bfd['peer'].items():
            # IPv6 link local peers require an explicit local address/interface
            if is_ipv6_link_local(peer):
                if 'source' not in peer_config or len(peer_config['source']) < 2:
                    raise ConfigError('BFD IPv6 link-local peers require explicit local address and interface setting')

            # IPv6 peers require an explicit local address
            if is_ipv6(peer):
                if 'source' not in peer_config or 'address' not in peer_config['source']:
                    raise ConfigError('BFD IPv6 peers require explicit local address setting')

            if 'multihop' in peer_config:
                # multihop require source address
                if 'source' not in peer_config or 'address' not in peer_config['source']:
                    raise ConfigError('BFD multihop require source address')

                # multihop and echo-mode cannot be used together
                if 'echo_mode' in peer_config:
                    raise ConfigError('BFD multihop and echo-mode cannot be used together')

                # multihop doesn't accept interface names
                if 'source' in peer_config and 'interface' in peer_config['source']:
                    raise ConfigError('BFD multihop and source interface cannot be used together')

            if 'minimum_ttl' in peer_config and 'multihop' not in peer_config:
                raise ConfigError('Minimum TTL is only available for multihop BFD sessions!')

            if 'profile' in peer_config:
                profile_name = peer_config['profile']
                if 'profile' not in bfd or profile_name not in bfd['profile']:
                    raise ConfigError(f'BFD profile "{profile_name}" does not exist!')

            if 'vrf' in peer_config:
                verify_vrf(peer_config)

    return None

def generate(config_dict):
    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().generate(config_dict)

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
