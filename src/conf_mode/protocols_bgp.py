#!/usr/bin/env python3
#
# Copyright (C) 2020-2022 VyOS maintainers and contributors
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
from vyos.configverify import verify_vrf
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
        if not vrf:
            # We are running in the default VRF context, thus we can not delete
            # our main BGP instance if there are dependent BGP VRF instances.
            bgp['dependent_vrfs'] = conf.get_config_dict(['vrf', 'name'],
                key_mangling=('-', '_'), get_first_key=True, no_tag_node_value_mangle=True)
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
        if 'dependent_vrfs' in bgp:
            for vrf, vrf_options in bgp['dependent_vrfs'].items():
                if dict_search('protocols.bgp', vrf_options) != None:
                    raise ConfigError('Cannot delete default BGP instance, ' \
                                      'dependent VRF instance(s) exist!')
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
                    raise ConfigError(f'Only one local-as number can be specified for peer "{peer}"!')

                # Neighbor local-as override can not be the same as the local-as
                # we use for this BGP instane!
                asn = list(peer_config['local_as'].keys())[0]
                if asn == bgp['local_as']:
                    raise ConfigError('Cannot have local-as same as BGP AS number')

                # Neighbor AS specified for local-as and remote-as can not be the same
                if dict_search('remote_as', peer_config) == asn:
                     raise ConfigError(f'Neighbor "{peer}" has local-as specified which is '\
                                        'the same as remote-as, this is not allowed!')

            # ttl-security and ebgp-multihop can't be used in the same configration
            if 'ebgp_multihop' in peer_config and 'ttl_security' in peer_config:
                raise ConfigError('You can not set both ebgp-multihop and ttl-security hops')

            # Check if neighbor has both override capability and strict capability match
            # configured at the same time.
            if 'override_capability' in peer_config and 'strict_capability_match' in peer_config:
                raise ConfigError(f'Neighbor "{peer}" cannot have both override-capability and '\
                                  'strict-capability-match configured at the same time!')

            # Check spaces in the password
            if 'password' in peer_config and ' ' in peer_config['password']:
                raise ConfigError('Whitespace is not allowed in passwords!')

            # Some checks can/must only be done on a neighbor and not a peer-group
            if neighbor == 'neighbor':
                # remote-as must be either set explicitly for the neighbor
                # or for the entire peer-group
                if not verify_remote_as(peer_config, bgp):
                    raise ConfigError(f'Neighbor "{peer}" remote-as must be set!')

                # Peer-group member cannot override remote-as of peer-group
                if 'peer_group' in peer_config:
                    peer_group = peer_config['peer_group']
                    if 'remote_as' in peer_config and 'remote_as' in bgp['peer_group'][peer_group]:
                        raise ConfigError(f'Peer-group member "{peer}" cannot override remote-as of peer-group "{peer_group}"!')
                if 'interface' in peer_config:
                    if 'peer_group' in peer_config['interface']:
                        peer_group = peer_config['interface']['peer_group']
                        if 'remote_as' in peer_config['interface'] and 'remote_as' in bgp['peer_group'][peer_group]:
                            raise ConfigError(f'Peer-group member "{peer}" cannot override remote-as of peer-group "{peer_group}"!')
                    if 'v6only' in peer_config['interface']:
                        if 'peer_group' in peer_config['interface']['v6only']:
                            peer_group = peer_config['interface']['v6only']['peer_group']
                            if 'remote_as' in peer_config['interface']['v6only'] and 'remote_as' in bgp['peer_group'][peer_group]:
                                raise ConfigError(f'Peer-group member "{peer}" cannot override remote-as of peer-group "{peer_group}"!')

                # Only checks for ipv4 and ipv6 neighbors
                # Check if neighbor address is assigned as system interface address
                vrf = None
                vrf_error_msg = f' in default VRF!'
                if 'vrf' in bgp:
                    vrf = bgp['vrf']
                    vrf_error_msg = f' in VRF "{vrf}"!'

                if is_ip(peer) and is_addr_assigned(peer, vrf):
                    raise ConfigError(f'Can not configure local address as neighbor "{peer}"{vrf_error_msg}')
                elif is_interface(peer):
                    if 'peer_group' in peer_config:
                        raise ConfigError(f'peer-group must be set under the interface node of "{peer}"')
                    if 'remote_as' in peer_config:
                        raise ConfigError(f'remote-as must be set under the interface node of "{peer}"')
                    if 'source_interface' in peer_config['interface']:
                        raise ConfigError(f'"source-interface" option not allowed for neighbor "{peer}"')

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

                if 'conditionally_advertise' in afi_config:
                    if 'advertise_map' not in afi_config['conditionally_advertise']:
                        raise ConfigError('Must speficy advertise-map when conditionally-advertise is in use!')
                    # Verify advertise-map (which is a route-map) exists
                    verify_route_map(afi_config['conditionally_advertise']['advertise_map'], bgp)

                    if ('exist_map' not in afi_config['conditionally_advertise'] and
                        'non_exist_map' not in afi_config['conditionally_advertise']):
                        raise ConfigError('Must either speficy exist-map or non-exist-map when ' \
                                          'conditionally-advertise is in use!')

                    if {'exist_map', 'non_exist_map'} <= set(afi_config['conditionally_advertise']):
                        raise ConfigError('Can not specify both exist-map and non-exist-map for ' \
                                          'conditionally-advertise!')

                    if 'exist_map' in afi_config['conditionally_advertise']:
                        verify_route_map(afi_config['conditionally_advertise']['exist_map'], bgp)

                    if 'non_exist_map' in afi_config['conditionally_advertise']:
                        verify_route_map(afi_config['conditionally_advertise']['non_exist_map'], bgp)

                # T4332: bgp deterministic-med cannot be disabled while addpath-tx-bestpath-per-AS is in use
                if 'addpath_tx_per_as' in afi_config:
                    if dict_search('parameters.deterministic_med', bgp) == None:
                        raise ConfigError('addpath-tx-per-as requires BGP deterministic-med paramtere to be set!')

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
    if dict_search('parameters.distance.global', bgp) != None:
        for key in ['external', 'internal', 'local']:
            if dict_search(f'parameters.distance.global.{key}', bgp) == None:
                raise ConfigError('Missing mandatory configuration option for '\
                                 f'global administrative distance {key}!')

    # Address Family specific validation
    if 'address_family' in bgp:
        for afi, afi_config in bgp['address_family'].items():
            if 'distance' in afi_config:
                # Throw an error if the address family specific administrative
                # distance parameters aren't all filled out.
                for key in ['external', 'internal', 'local']:
                    if key not in afi_config['distance']:
                        raise ConfigError('Missing mandatory configuration option for '\
                                         f'{afi} administrative distance {key}!')

            if afi in ['ipv4_unicast', 'ipv6_unicast']:
                if 'import' in afi_config and 'vrf' in afi_config['import']:
                    # Check if VRF exists
                    verify_vrf(afi_config['import']['vrf'])

                    # FRR error: please unconfigure vpn to vrf commands before
                    # using import vrf commands
                    if 'vpn' in afi_config['import'] or dict_search('export.vpn', afi_config) != None:
                        raise ConfigError('Please unconfigure VPN to VRF commands before '\
                                          'using "import vrf" commands!')

                # Verify that the export/import route-maps do exist
                for export_import in ['export', 'import']:
                    tmp = dict_search(f'route_map.vpn.{export_import}', afi_config)
                    if tmp: verify_route_map(tmp, bgp)


    return None

def generate(bgp):
    if not bgp or 'deleted' in bgp:
        return None

    bgp['protocol'] = 'bgp' # required for frr/vrf.route-map.frr.j2
    bgp['frr_zebra_config'] = render_to_string('frr/vrf.route-map.frr.j2', bgp)
    bgp['frr_bgpd_config']  = render_to_string('frr/bgpd.frr.j2', bgp)

    return None

def apply(bgp):
    bgp_daemon = 'bgpd'
    zebra_daemon = 'zebra'

    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()

    # The route-map used for the FIB (zebra) is part of the zebra daemon
    frr_cfg.load_configuration(zebra_daemon)
    frr_cfg.modify_section(r'(\s+)?ip protocol bgp route-map [-a-zA-Z0-9.]+', stop_pattern='(\s|!)')
    if 'frr_zebra_config' in bgp:
        frr_cfg.add_before(frr.default_add_before, bgp['frr_zebra_config'])
    frr_cfg.commit_configuration(zebra_daemon)

    # Generate empty helper string which can be ammended to FRR commands, it
    # will be either empty (default VRF) or contain the "vrf <name" statement
    vrf = ''
    if 'vrf' in bgp:
        vrf = ' vrf ' + bgp['vrf']

    frr_cfg.load_configuration(bgp_daemon)
    frr_cfg.modify_section(f'^router bgp \d+{vrf}', stop_pattern='^exit', remove_stop_mark=True)
    if 'frr_bgpd_config' in bgp:
        frr_cfg.add_before(frr.default_add_before, bgp['frr_bgpd_config'])
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
