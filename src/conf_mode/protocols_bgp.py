#!/usr/bin/env python3
#
# Copyright (C) 2020-2021 VyOS maintainers and contributors
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
from sys import argv

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configverify import verify_prefix_list
from vyos.configverify import verify_route_map
from vyos.template import is_ip
from vyos.template import is_interface
from vyos.template import render_to_string
from vyos.util import dict_search
from vyos.validate import is_addr_assigned
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    vrf = None
    if len(argv) > 1:
        vrf = argv[1]

    base_path = ['protocols', 'bgp']

    # eqivalent of the C foo ? 'a' : 'b' statement
    base = vrf and ['vrf', 'name', vrf, 'protocols', 'bgp'] or base_path
    bgp = conf.get_config_dict(base, key_mangling=('-', '_'),
                               get_first_key=True, no_tag_node_value_mangle=True)

    # Assign the name of our VRF context. This MUST be done before the return
    # statement below, else on deletion we will delete the default instance
    # instead of the VRF instance.
    if vrf: bgp.update({'vrf' : vrf})

    if not conf.exists(base):
        bgp.update({'deleted' : ''})
        return bgp

    # We also need some additional information from the config, prefix-lists
    # and route-maps for instance. They will be used in verify().
    #
    # XXX: one MUST always call this without the key_mangling() option! See
    # vyos.configverify.verify_common_route_maps() for more information.
    tmp = conf.get_config_dict(['policy'])
    # Merge policy dict into "regular" config dict
    bgp = dict_merge(tmp, bgp)

    return bgp

def verify_remote_as(peer_config, bgp_config):
    if 'remote_as' in peer_config:
        return peer_config['remote_as']

    if 'peer_group' in peer_config:
        peer_group_name = peer_config['peer_group']
        tmp = dict_search(f'peer_group.{peer_group_name}.remote_as', bgp_config)
        if tmp: return tmp

    if 'interface' in peer_config:
        if 'remote_as' in peer_config['interface']:
            return peer_config['interface']['remote_as']

        if 'peer_group' in peer_config['interface']:
            peer_group_name = peer_config['interface']['peer_group']
            tmp = dict_search(f'peer_group.{peer_group_name}.remote_as', bgp_config)
            if tmp: return tmp

        if 'v6only' in peer_config['interface']:
            if 'remote_as' in peer_config['interface']['v6only']:
                return peer_config['interface']['v6only']['remote_as']

    return None

def verify(bgp):
    if not bgp or 'deleted' in bgp:
        return None

    if 'local_as' not in bgp:
        raise ConfigError('BGP local-as number must be defined!')

    # Common verification for both peer-group and neighbor statements
    for neighbor in ['neighbor', 'peer_group']:
        # bail out early if there is no neighbor or peer-group statement
        # this also saves one indention level
        if neighbor not in bgp:
            continue

        for peer, peer_config in bgp[neighbor].items():
            # Only regular "neighbor" statement can have a peer-group set
            # Check if the configure peer-group exists
            if 'peer_group' in peer_config:
                peer_group = peer_config['peer_group']
                if 'peer_group' not in bgp or peer_group not in bgp['peer_group']:
                    raise ConfigError(f'Specified peer-group "{peer_group}" for '\
                                      f'neighbor "{neighbor}" does not exist!')

            if 'local_as' in peer_config:
                if len(peer_config['local_as']) > 1:
                    raise ConfigError('Only one local-as number may be specified!')

                # Neighbor local-as override can not be the same as the local-as
                # we use for this BGP instane!
                asn = list(peer_config['local_as'].keys())[0]
                if asn == bgp['local_as']:
                    raise ConfigError('Cannot have local-as same as BGP AS number')

            # ttl-security and ebgp-multihop can't be used in the same configration
            if 'ebgp_multihop' in peer_config and 'ttl_security' in peer_config:
                raise ConfigError('You can\'t set both ebgp-multihop and ttl-security hops')

            # Check if neighbor has both override capability and strict capability match configured at the same time.
            if 'override_capability' in peer_config and 'strict_capability_match' in peer_config:
                raise ConfigError(f'Neighbor "{peer}" cannot have both override-capability and strict-capability-match configured at the same time!')

            # Check spaces in the password
            if 'password' in peer_config and ' ' in peer_config['password']:
                raise ConfigError('You can\'t use spaces in the password')

            # Some checks can/must only be done on a neighbor and not a peer-group
            if neighbor == 'neighbor':
                # remote-as must be either set explicitly for the neighbor
                # or for the entire peer-group
                if not verify_remote_as(peer_config, bgp):
                    raise ConfigError(f'Neighbor "{peer}" remote-as must be set!')

                # Only checks for ipv4 and ipv6 neighbors
                # Check if neighbor address is assigned as system interface address
                if is_ip(peer) and is_addr_assigned(peer):
                    raise ConfigError(f'Can not configure a local address as neighbor "{peer}"')
                elif is_interface(peer):
                    if 'peer_group' in peer_config:
                        raise ConfigError(f'peer-group must be set under the interface node of "{peer}"')
                    if 'remote_as' in peer_config:
                        raise ConfigError(f'remote-as must be set under the interface node of "{peer}"')

            for afi in ['ipv4_unicast', 'ipv4_multicast', 'ipv4_labeled_unicast', 'ipv4_flowspec',
                        'ipv6_unicast', 'ipv6_multicast', 'ipv6_labeled_unicast', 'ipv6_flowspec',
                        'l2vpn_evpn']:
                # Bail out early if address family is not configured
                if 'address_family' not in peer_config or afi not in peer_config['address_family']:
                    continue

                # Check if neighbor has both ipv4 unicast and ipv4 labeled unicast configured at the same time.
                if 'ipv4_unicast' in peer_config['address_family'] and 'ipv4_labeled_unicast' in peer_config['address_family']:
                    raise ConfigError(f'Neighbor "{peer}" cannot have both ipv4-unicast and ipv4-labeled-unicast configured at the same time!')

                # Check if neighbor has both ipv6 unicast and ipv6 labeled unicast configured at the same time.
                if 'ipv6_unicast' in peer_config['address_family'] and 'ipv6_labeled_unicast' in peer_config['address_family']:
                    raise ConfigError(f'Neighbor "{peer}" cannot have both ipv6-unicast and ipv6-labeled-unicast configured at the same time!')

                afi_config = peer_config['address_family'][afi]
                # Validate if configured Prefix list exists
                if 'prefix_list' in afi_config:
                    for tmp in ['import', 'export']:
                        if tmp not in afi_config['prefix_list']:
                            # bail out early
                            continue
                        if afi == 'ipv4_unicast':
                            verify_prefix_list(afi_config['prefix_list'][tmp], bgp)
                        elif afi == 'ipv6_unicast':
                            verify_prefix_list(afi_config['prefix_list'][tmp], bgp, version='6')

                if 'route_map' in afi_config:
                    for tmp in ['import', 'export']:
                        if tmp in afi_config['route_map']:
                            verify_route_map(afi_config['route_map'][tmp], bgp)

                if 'route_reflector_client' in afi_config:
                    if 'remote_as' in peer_config and peer_config['remote_as'] != 'internal' and peer_config['remote_as'] != bgp['local_as']:
                        raise ConfigError('route-reflector-client only supported for iBGP peers')
                    else:
                        if 'peer_group' in peer_config:
                            peer_group_as = dict_search(f'peer_group.{peer_group}.remote_as', bgp)
                            if peer_group_as != None and peer_group_as != 'internal' and peer_group_as != bgp['local_as']:
                                raise ConfigError('route-reflector-client only supported for iBGP peers')

    # Throw an error if a peer group is not configured for allow range
    for prefix in dict_search('listen.range', bgp) or []:
        # we can not use dict_search() here as prefix contains dots ...
        if 'peer_group' not in bgp['listen']['range'][prefix]:
            raise ConfigError(f'Listen range for prefix "{prefix}" has no peer group configured.')

        peer_group = bgp['listen']['range'][prefix]['peer_group']
        if 'peer_group' not in bgp or peer_group not in bgp['peer_group']:
            raise ConfigError(f'Peer-group "{peer_group}" for listen range "{prefix}" does not exist!')

        if not verify_remote_as(bgp['listen']['range'][prefix], bgp):
            raise ConfigError(f'Peer-group "{peer_group}" requires remote-as to be set!')

    # Throw an error if the global administrative distance parameters aren't all filled out.
    if dict_search('parameters.distance', bgp) == None:
        pass
    else:
        if dict_search('parameters.distance.global', bgp):
            for key in ['external', 'internal', 'local']:
                if dict_search(f'parameters.distance.global.{key}', bgp) == None:
                    raise ConfigError('Missing mandatory configuration option for '\
                                     f'global administrative distance {key}!')

    # Throw an error if the address family specific administrative distance parameters aren't all filled out.
    if dict_search('address_family', bgp) == None:
        pass
    else:
        for address_family_name in dict_search('address_family', bgp):
            if dict_search(f'address_family.{address_family_name}.distance', bgp) == None:
                pass
            else:
                for key in ['external', 'internal', 'local']:
                    if dict_search(f'address_family.{address_family_name}.distance.{key}', bgp) == None:
                        raise ConfigError('Missing mandatory configuration option for '\
                                         f'{address_family_name} administrative distance {key}!')

    return None

def generate(bgp):
    if not bgp or 'deleted' in bgp:
        bgp['frr_bgpd_config'] = ''
        bgp['frr_zebra_config'] = ''
        return None

    bgp['protocol'] = 'bgp' # required for frr/vrf.route-map.frr.tmpl
    bgp['frr_zebra_config'] = render_to_string('frr/vrf.route-map.frr.tmpl', bgp)
    bgp['frr_bgpd_config']  = render_to_string('frr/bgpd.frr.tmpl', bgp)

    return None

def apply(bgp):
    bgp_daemon = 'bgpd'
    zebra_daemon = 'zebra'

    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()

    # The route-map used for the FIB (zebra) is part of the zebra daemon
    frr_cfg.load_configuration(zebra_daemon)
    frr_cfg.modify_section(r'(\s+)?ip protocol bgp route-map [-a-zA-Z0-9.]+$', '', '(\s|!)')
    frr_cfg.add_before(r'(ip prefix-list .*|route-map .*|line vty)', bgp['frr_zebra_config'])
    frr_cfg.commit_configuration(zebra_daemon)

    # Generate empty helper string which can be ammended to FRR commands, it
    # will be either empty (default VRF) or contain the "vrf <name" statement
    vrf = ''
    if 'vrf' in bgp:
        vrf = ' vrf ' + bgp['vrf']

    frr_cfg.load_configuration(bgp_daemon)
    frr_cfg.modify_section(f'^router bgp \d+{vrf}$', '')
    frr_cfg.add_before(r'(ip prefix-list .*|route-map .*|line vty)', bgp['frr_bgpd_config'])
    frr_cfg.commit_configuration(bgp_daemon)

    # If FRR config is blank, re-run the blank commit x times due to frr-reload
    # behavior/bug not properly clearing out on one commit.
    if bgp['frr_bgpd_config'] == '':
        for a in range(5):
            frr_cfg.commit_configuration(bgp_daemon)
    if bgp['frr_zebra_config'] == '':
        for a in range(5):
            frr_cfg.commit_configuration(zebra_daemon)

    # Save configuration to /run/frr/config/frr.conf
    frr.save_configuration()

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
