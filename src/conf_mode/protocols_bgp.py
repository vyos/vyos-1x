#!/usr/bin/env python3
#
# Copyright (C) 2020-2024 VyOS maintainers and contributors
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
from sys import argv

from vyos.base import Warning
from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configdict import node_changed
from vyos.configverify import verify_prefix_list
from vyos.configverify import verify_route_map
from vyos.configverify import verify_vrf
from vyos.template import is_ip
from vyos.template import is_interface
from vyos.template import render_to_string
from vyos.utils.dict import dict_search
from vyos.utils.network import get_interface_vrf
from vyos.utils.network import is_addr_assigned
from vyos.utils.process import process_named_running
from vyos.utils.process import call
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

    bgp['dependent_vrfs'] = conf.get_config_dict(['vrf', 'name'],
                                                 key_mangling=('-', '_'),
                                                 get_first_key=True,
                                                 no_tag_node_value_mangle=True)

    # Remove per interface MPLS configuration - get a list if changed
    # nodes under the interface tagNode
    interfaces_removed = node_changed(conf, base + ['interface'])
    if interfaces_removed:
        bgp['interface_removed'] = list(interfaces_removed)

    # Assign the name of our VRF context. This MUST be done before the return
    # statement below, else on deletion we will delete the default instance
    # instead of the VRF instance.
    if vrf:
        bgp.update({'vrf' : vrf})
        # We can not delete the BGP VRF instance if there is a L3VNI configured
        # FRR L3VNI must be deleted first otherwise we will see error:
        # "FRR error: Please unconfigure l3vni 3000"
        tmp = ['vrf', 'name', vrf, 'vni']
        if conf.exists_effective(tmp):
            bgp.update({'vni' : conf.return_effective_value(tmp)})
        # We can safely delete ourself from the dependent vrf list
        if vrf in bgp['dependent_vrfs']:
            del bgp['dependent_vrfs'][vrf]

        bgp['dependent_vrfs'].update({'default': {'protocols': {
            'bgp': conf.get_config_dict(base_path, key_mangling=('-', '_'),
                                        get_first_key=True,
                                        no_tag_node_value_mangle=True)}}})

    if not conf.exists(base):
        # If bgp instance is deleted then mark it
        bgp.update({'deleted' : ''})
        return bgp

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    bgp = conf.merge_defaults(bgp, recursive=True)

    # We also need some additional information from the config, prefix-lists
    # and route-maps for instance. They will be used in verify().
    #
    # XXX: one MUST always call this without the key_mangling() option! See
    # vyos.configverify.verify_common_route_maps() for more information.
    tmp = conf.get_config_dict(['policy'])
    # Merge policy dict into "regular" config dict
    bgp = dict_merge(tmp, bgp)

    return bgp


def verify_vrf_as_import(search_vrf_name: str, afi_name: str, vrfs_config: dict) -> bool:
    """
    :param search_vrf_name: search vrf name in import list
    :type search_vrf_name: str
    :param afi_name: afi/safi name
    :type afi_name: str
    :param vrfs_config: configuration dependents vrfs
    :type vrfs_config: dict
    :return: if vrf in import list retrun true else false
    :rtype: bool
    """
    for vrf_name, vrf_config in vrfs_config.items():
        import_list = dict_search(
            f'protocols.bgp.address_family.{afi_name}.import.vrf',
            vrf_config)
        if import_list:
            if search_vrf_name in import_list:
               return True
    return False

def verify_vrf_import_options(afi_config: dict) -> bool:
    """
    Search if afi contains one of options
    :param afi_config: afi/safi
    :type afi_config: dict
    :return: if vrf contains rd and route-target options return true else false
    :rtype: bool
    """
    options = [
        f'rd.vpn.export',
        f'route_target.vpn.import',
        f'route_target.vpn.export',
        f'route_target.vpn.both'
    ]
    for option in options:
        if dict_search(option, afi_config):
            return True
    return False

def verify_vrf_import(vrf_name: str, vrfs_config: dict, afi_name: str) -> bool:
    """
    Verify if vrf exists and contain options
    :param vrf_name: name of VRF
    :type vrf_name: str
    :param vrfs_config: dependent vrfs config
    :type vrfs_config: dict
    :param afi_name: afi/safi name
    :type afi_name: str
    :return: if vrf contains rd and route-target options return true else false
    :rtype: bool
    """
    if vrf_name != 'default':
        verify_vrf({'vrf': vrf_name})
    if dict_search(f'{vrf_name}.protocols.bgp.address_family.{afi_name}',
                   vrfs_config):
        afi_config = \
        vrfs_config[vrf_name]['protocols']['bgp']['address_family'][
            afi_name]
        if verify_vrf_import_options(afi_config):
            return True
    return False

def verify_vrflist_import(afi_name: str, afi_config: dict, vrfs_config: dict) -> bool:
    """
    Call function to verify
    if scpecific vrf contains rd and route-target
    options return true else false

    :param afi_name: afi/safi name
    :type afi_name: str
    :param afi_config: afi/safi configuration
    :type afi_config: dict
    :param vrfs_config: dependent vrfs config
    :type vrfs_config:dict
    :return: if vrf contains rd and route-target options return true else false
    :rtype: bool
    """
    for vrf_name in afi_config['import']['vrf']:
        if verify_vrf_import(vrf_name, vrfs_config, afi_name):
            return True
    return False

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
            if 'peer_group' in peer_config['interface']['v6only']:
                peer_group_name = peer_config['interface']['v6only']['peer_group']
                tmp = dict_search(f'peer_group.{peer_group_name}.remote_as', bgp_config)
                if tmp: return tmp

    return None

def verify_afi(peer_config, bgp_config):
    # If address_family configured under neighboor
    if 'address_family' in peer_config:
        return True

    # If address_family configured under peer-group
    # if neighbor interface configured
    peer_group_name = None
    if dict_search('interface.peer_group', peer_config):
        peer_group_name = peer_config['interface']['peer_group']
    elif dict_search('interface.v6only.peer_group', peer_config):
        peer_group_name = peer_config['interface']['v6only']['peer_group']

    # if neighbor IP configured.
    if 'peer_group' in peer_config:
        peer_group_name = peer_config['peer_group']
    if peer_group_name:
        tmp = dict_search(f'peer_group.{peer_group_name}.address_family', bgp_config)
        if tmp: return True
    return False

def verify(bgp):
    if 'deleted' in bgp:
        if 'vrf' in bgp:
            # Cannot delete vrf if it exists in import vrf list in other vrfs
            for tmp_afi in ['ipv4_unicast', 'ipv6_unicast']:
                if verify_vrf_as_import(bgp['vrf'], tmp_afi, bgp['dependent_vrfs']):
                    raise ConfigError(f'Cannot delete VRF instance "{bgp["vrf"]}", ' \
                                      'unconfigure "import vrf" commands!')
        else:
            # We are running in the default VRF context, thus we can not delete
            # our main BGP instance if there are dependent BGP VRF instances.
            if 'dependent_vrfs' in bgp:
                for vrf, vrf_options in bgp['dependent_vrfs'].items():
                    if vrf != 'default':
                        if dict_search('protocols.bgp', vrf_options):
                            raise ConfigError('Cannot delete default BGP instance, ' \
                                              'dependent VRF instance(s) exist(s)!')
                        if 'vni' in vrf_options:
                            raise ConfigError('Cannot delete default BGP instance, ' \
                                              'dependent L3VNI exists!')

        return None

    if 'system_as' not in bgp:
        raise ConfigError('BGP system-as number must be defined!')

    # Verify BMP
    if 'bmp' in bgp:
        # check bmp flag "bgpd -d -F traditional --daemon -A 127.0.0.1 -M rpki -M bmp"
        if not process_named_running('bgpd', 'bmp'):
            raise ConfigError(
                f'"bmp" flag is not found in bgpd. Configure "set system frr bmp" and restart bgp process'
            )
        # check bmp target
        if 'target' in bgp['bmp']:
            for target, target_config in bgp['bmp']['target'].items():
                if 'address' not in target_config:
                    raise ConfigError(f'BMP target "{target}" address must be defined!')

    # Verify vrf on interface and bgp section
    if 'interface' in bgp:
        for interface in bgp['interface']:
            error_msg = f'Interface "{interface}" belongs to different VRF instance'
            tmp = get_interface_vrf(interface)
            if 'vrf' in bgp:
                if bgp['vrf'] != tmp:
                    vrf = bgp['vrf']
                    raise ConfigError(f'{error_msg} "{vrf}"!')
            elif tmp != 'default':
                raise ConfigError(f'{error_msg} "{tmp}"!')

    peer_groups_context = dict()
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

                if 'remote_as' in peer_config:
                    is_ibgp = True
                    if peer_config['remote_as'] != 'internal' and \
                            peer_config['remote_as'] != bgp['system_as']:
                        is_ibgp = False

                    if peer_group not in peer_groups_context:
                        peer_groups_context[peer_group] = is_ibgp
                    elif peer_groups_context[peer_group] != is_ibgp:
                        raise ConfigError(f'Peer-group members must be '
                                          f'all internal or all external')

            if 'local_role' in peer_config:
                #Ensure Local Role has only one value.
                if len(peer_config['local_role']) > 1:
                    raise ConfigError(f'Only one local role can be specified for peer "{peer}"!')

            if 'local_as' in peer_config:
                if len(peer_config['local_as']) > 1:
                    raise ConfigError(f'Only one local-as number can be specified for peer "{peer}"!')

                # Neighbor local-as override can not be the same as the local-as
                # we use for this BGP instane!
                asn = list(peer_config['local_as'].keys())[0]
                if asn == bgp['system_as']:
                    raise ConfigError('Cannot have local-as same as system-as number')

                # Neighbor AS specified for local-as and remote-as can not be the same
                if dict_search('remote_as', peer_config) == asn and neighbor != 'peer_group':
                     raise ConfigError(f'Neighbor "{peer}" has local-as specified which is '\
                                        'the same as remote-as, this is not allowed!')

            # ttl-security and ebgp-multihop can't be used in the same configration
            if 'ebgp_multihop' in peer_config and 'ttl_security' in peer_config:
                raise ConfigError('You can not set both ebgp-multihop and ttl-security hops')

            # interface and ebgp-multihop can't be used in the same configration
            if 'ebgp_multihop' in peer_config and 'interface' in peer_config:
                raise ConfigError(f'Ebgp-multihop can not be used with directly connected '\
                                  f'neighbor "{peer}"')

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

                if not verify_afi(peer_config, bgp):
                    Warning(f'BGP neighbor "{peer}" requires address-family!')

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

            # Local-AS allowed only for EBGP peers
            if 'local_as' in peer_config:
                remote_as = verify_remote_as(peer_config, bgp)
                if remote_as == bgp['system_as']:
                    raise ConfigError(f'local-as configured for "{peer}", allowed only for eBGP peers!')

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
                    peer_group_as = peer_config.get('remote_as')

                    if peer_group_as is None or (peer_group_as != 'internal' and peer_group_as != bgp['system_as']):
                        raise ConfigError('route-reflector-client only supported for iBGP peers')
                    else:
                        if 'peer_group' in peer_config:
                            peer_group_as = dict_search(f'peer_group.{peer_group}.remote_as', bgp)
                            if peer_group_as is None or (peer_group_as != 'internal' and peer_group_as != bgp['system_as']):
                                raise ConfigError('route-reflector-client only supported for iBGP peers')

            # T5833 not all AFIs are supported for VRF
            if 'vrf' in bgp and 'address_family' in peer_config:
                unsupported_vrf_afi = {
                    'ipv4_flowspec',
                    'ipv6_flowspec',
                    'ipv4_labeled_unicast',
                    'ipv6_labeled_unicast',
                    'ipv4_vpn',
                    'ipv6_vpn',
                }
                for afi in peer_config['address_family']:
                    if afi in unsupported_vrf_afi:
                        raise ConfigError(
                            f"VRF is not allowed for address-family '{afi.replace('_', '-')}'"
                        )

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

    # TCP keepalive requires all three parameters to be set
    if dict_search('parameters.tcp_keepalive', bgp) != None:
        if not {'idle', 'interval', 'probes'} <= set(bgp['parameters']['tcp_keepalive']):
            raise ConfigError('TCP keepalive incomplete - idle, keepalive and probes must be set')

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
                vrf_name = bgp['vrf'] if dict_search('vrf', bgp) else 'default'
                # Verify if currant VRF contains rd and route-target options
                # and does not exist in import list in other VRFs
                if dict_search(f'rd.vpn.export', afi_config):
                    if verify_vrf_as_import(vrf_name, afi, bgp['dependent_vrfs']):
                        raise ConfigError(
                            'Command "import vrf" conflicts with "rd vpn export" command!')
                    if not dict_search('parameters.router_id', bgp):
                        Warning(f'BGP "router-id" is required when using "rd" and "route-target"!')

                if dict_search('route_target.vpn.both', afi_config):
                    if verify_vrf_as_import(vrf_name, afi, bgp['dependent_vrfs']):
                        raise ConfigError(
                            'Command "import vrf" conflicts with "route-target vpn both" command!')
                    if dict_search('route_target.vpn.export', afi_config):
                        raise ConfigError(
                            'Command "route-target vpn export" conflicts '\
                            'with "route-target vpn both" command!')
                    if dict_search('route_target.vpn.import', afi_config):
                        raise ConfigError(
                            'Command "route-target vpn import" conflicts '\
                            'with "route-target vpn both" command!')

                if dict_search('route_target.vpn.import', afi_config):
                    if verify_vrf_as_import(vrf_name, afi, bgp['dependent_vrfs']):
                        raise ConfigError(
                            'Command "import vrf conflicts" with "route-target vpn import" command!')

                if dict_search('route_target.vpn.export', afi_config):
                    if verify_vrf_as_import(vrf_name, afi, bgp['dependent_vrfs']):
                        raise ConfigError(
                            'Command "import vrf" conflicts with "route-target vpn export" command!')

                # Verify if VRFs in import do not contain rd
                # and route-target options
                if dict_search('import.vrf', afi_config) is not None:
                    # Verify if VRF with import does not contain rd
                    # and route-target options
                    if verify_vrf_import_options(afi_config):
                        raise ConfigError(
                            'Please unconfigure "import vrf" commands before using vpn commands in the same VRF!')
                    # Verify if VRFs in import list do not contain rd
                    # and route-target options
                    if verify_vrflist_import(afi, afi_config, bgp['dependent_vrfs']):
                        raise ConfigError(
                            'Please unconfigure import vrf commands before using vpn commands in dependent VRFs!')

                    # FRR error: please unconfigure vpn to vrf commands before
                    # using import vrf commands
                    if 'vpn' in afi_config['import'] or dict_search('export.vpn', afi_config) != None:
                        raise ConfigError('Please unconfigure VPN to VRF commands before '\
                                          'using "import vrf" commands!')

                # Verify that the export/import route-maps do exist
                for export_import in ['export', 'import']:
                    tmp = dict_search(f'route_map.vpn.{export_import}', afi_config)
                    if tmp: verify_route_map(tmp, bgp)

                # per-vrf sid and per-af sid are mutually exclusive
                if 'sid' in afi_config and 'sid' in bgp:
                    raise ConfigError('SID per VRF and SID per address-family are mutually exclusive!')

            # Checks only required for L2VPN EVPN
            if afi in ['l2vpn_evpn']:
                if 'vni' in afi_config:
                    for vni, vni_config in afi_config['vni'].items():
                        if 'rd' in vni_config and 'advertise_all_vni' not in afi_config:
                            raise ConfigError('BGP EVPN "rd" requires "advertise-all-vni" to be set!')
                        if 'route_target' in vni_config and 'advertise_all_vni' not in afi_config:
                            raise ConfigError('BGP EVPN "route-target" requires "advertise-all-vni" to be set!')

    return None

def generate(bgp):
    if not bgp or 'deleted' in bgp:
        return None

    bgp['frr_bgpd_config']  = render_to_string('frr/bgpd.frr.j2', bgp)
    return None

def apply(bgp):
    if 'deleted' in bgp:
        # We need to ensure that the L3VNI is deleted first.
        # This is not possible with old config backend
        # priority bug
        if {'vrf', 'vni'} <= set(bgp):
            call('vtysh -c "conf t" -c "vrf {vrf}" -c "no vni {vni}"'.format(**bgp))

    bgp_daemon = 'bgpd'

    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()

    # Generate empty helper string which can be ammended to FRR commands, it
    # will be either empty (default VRF) or contain the "vrf <name" statement
    vrf = ''
    if 'vrf' in bgp:
        vrf = ' vrf ' + bgp['vrf']

    frr_cfg.load_configuration(bgp_daemon)

    # Remove interface specific config
    for key in ['interface', 'interface_removed']:
        if key not in bgp:
            continue
        for interface in bgp[key]:
            frr_cfg.modify_section(f'^interface {interface}', stop_pattern='^exit', remove_stop_mark=True)

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
