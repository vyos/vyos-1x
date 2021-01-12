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

from sys import exit

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.template import render
from vyos.template import render_to_string
from vyos.util import call
from vyos.util import dict_search
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

config_file = r'/tmp/bgp.frr'

def get_config():
    conf = Config()
    base = ['protocols', 'nbgp']
    bgp = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    # XXX: any reason we can not move this into the FRR template?
    # we shall not call vtysh directly, especially not in get_config()
    if not conf.exists(base) or not conf.exists(base + ['route-map']):
        call('vtysh -c \"conf t\" -c \"no ip protocol bgp\"')
        return bgp

    # We also need some additional information from the config,
    # prefix-lists and route-maps for instance.
    base = ['policy']
    tmp = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    # As we only support one ASN (later checked in begin of verify()) we add the
    # new information only to the first AS number
    asn = next(iter(bgp))
    # Merge policy dict into bgp dict
    bgp[asn] = dict_merge(tmp, bgp[asn])

    return bgp

def verify(bgp):
    if not bgp:
        return None

    # Check if declared more than one ASN
    if len(bgp) > 1:
        raise ConfigError('Only one BGP AS number can be defined!')

    for asn, asn_config in bgp.items():
        import pprint
        pprint.pprint(asn_config)

        # Common verification for both peer-group and neighbor statements
        for neighbor in ['neighbor', 'peer_group']:
            # bail out early if there is no neighbor or peer-group statement
            # this also saves one indention level
            if neighbor not in asn_config:
                print(f'no {neighbor} found in config')
                continue

            for peer, peer_config in asn_config[neighbor].items():
                # Only regular "neighbor" statement can have a peer-group set
                # Check if the configure peer-group exists
                if 'peer_group' in peer_config:
                    peer_group = peer_config['peer_group']
                    if peer_group not in asn_config['peer_group']:
                        raise ConfigError(f'Specified peer-group "{peer_group}" for '\
                                          f'neighbor "{neighbor}" does not exist!')

                # Some checks can/must only be done on a neighbor and nor a peer-group
                if neighbor == 'neighbor':
                    # remote-as must be either set explicitly for the neighbor
                    # or for the entire peer-group
                    if 'remote_as' not in peer_config:
                        if 'peer_group' not in peer_config or 'remote_as' not in asn_config['peer_group'][peer_config['peer_group']]:
                            raise ConfigError('Remote AS must be set for neighbor or peer-group!')

                for afi in ['ipv4_unicast', 'ipv6_unicast']:
                    # Bail out early if address family is not configured
                    if 'address_family' not in peer_config or afi not in peer_config['address_family']:
                        continue

                    afi_config = peer_config['address_family'][afi]
                    # Validate if configured Prefix list exists
                    if 'prefix_list' in afi_config:
                        for tmp in ['import', 'export']:
                            if tmp in afi_config['prefix_list']:
                                if afi == 'ipv4_unicast':
                                    prefix_list = afi_config['prefix_list'][tmp]
                                    if 'prefix_list' not in asn_config or prefix_list not in asn_config['prefix_list']:
                                        raise ConfigError(f'prefix-list "{prefix_list}" used for "{tmp}" does not exist!')
                                if afi == 'ipv6_unicast':
                                    prefix_list = afi_config['prefix_list6'][tmp]
                                    if 'prefix_list6' not in asn_config or prefix_list not in asn_config['prefix_list6']:
                                        raise ConfigError(f'prefix-list "{prefix_list}" used for "{tmp}" does not exist!')


                    if 'route_map' in afi_config:
                        for tmp in ['import', 'export']:
                            if tmp in afi_config['route_map']:
                                route_map = afi_config['route_map'][tmp]
                                if 'route_map' not in asn_config or route_map not in asn_config['route_map']:
                                    raise ConfigError(f'route-map "{route_map}" used for "{tmp}" does not exist!')


    return None

def generate(bgp):
    if not bgp:
        bgp['new_frr_config'] = ''
        return None

    # only one BGP AS is supported, so we can directly send the first key
    # of the config dict
    asn = list(bgp.keys())[0]
    bgp[asn]['asn'] = asn

    # render(config) not needed, its only for debug
    render(config_file, 'frr/bgp.frr.tmpl', bgp[asn])
    bgp['new_frr_config'] = render_to_string('frr/bgp.frr.tmpl', bgp[asn])

    return None

def apply(bgp):
    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()
    frr_cfg.load_configuration(daemon='bgpd')
    frr_cfg.modify_section(f'router bgp \S+', '')
    frr_cfg.add_before(r'(ip prefix-list .*|route-map .*|line vty)', bgp['new_frr_config'])
    frr_cfg.commit_configuration(daemon='bgpd')

    # If FRR config is blank, rerun the blank commit x times due to frr-reload
    # behavior/bug not properly clearing out on one commit.
    if bgp['new_frr_config'] == '':
        for a in range(5):
            frr_cfg.commit_configuration(daemon='bgpd')

    # Debugging
    '''
    print('')
    print('--------- DEBUGGING ----------')
    print(f'Existing config:\n{frr_cfg["original_config"]}\n\n')
    print(f'Replacement config:\n{bgp["new_frr_config"]}\n\n')
    print(f'Modified config:\n{frr_cfg["modified_config"]}\n\n')
    '''

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
