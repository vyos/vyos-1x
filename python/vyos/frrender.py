# Copyright 2024-2025 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

"""
Library used to interface with FRRs mgmtd introduced in version 10.0
"""

import os

from time import sleep

from vyos.defaults import frr_debug_enable
from vyos.utils.dict import dict_search
from vyos.utils.file import write_file
from vyos.utils.process import cmd
from vyos.utils.process import rc_cmd
from vyos.template import render_to_string
from vyos import ConfigError

def debug(message):
    if not os.path.exists(frr_debug_enable):
        return
    print(message)

frr_protocols = ['babel', 'bfd', 'bgp', 'eigrp', 'isis', 'mpls', 'nhrp',
                 'openfabric', 'ospf', 'ospfv3', 'pim', 'pim6', 'rip',
                 'ripng', 'rpki', 'segment_routing', 'static']

babel_daemon = 'babeld'
bfd_daemon = 'bfdd'
bgp_daemon = 'bgpd'
isis_daemon = 'isisd'
ldpd_daemon = 'ldpd'
mgmt_daemon = 'mgmtd'
openfabric_daemon = 'fabricd'
ospf_daemon = 'ospfd'
ospf6_daemon = 'ospf6d'
pim_daemon = 'pimd'
pim6_daemon = 'pim6d'
rip_daemon = 'ripd'
ripng_daemon = 'ripngd'
zebra_daemon = 'zebra'
nhrp_daemon = 'nhrpd'

def get_frrender_dict(conf, argv=None) -> dict:
    from copy import deepcopy
    from vyos.config import config_dict_merge
    from vyos.configdict import get_dhcp_interfaces
    from vyos.configdict import get_pppoe_interfaces

    # We need to re-set the CLI path to the root level, as this function uses
    # conf.exists() with an absolute path form the CLI root
    conf.set_level([])

    # Create an empty dictionary which will be filled down the code path and
    # returned to the caller
    dict = {}

    if argv and len(argv) > 1:
        dict['vrf_context'] = argv[1]

    def dict_helper_ospf_defaults(ospf, path):
        # We have gathered the dict representation of the CLI, but there are default
        # options which we need to update into the dictionary retrived.
        default_values = conf.get_config_defaults(path, key_mangling=('-', '_'),
                                                  get_first_key=True, recursive=True)

        # We have to cleanup the default dict, as default values could enable features
        # which are not explicitly enabled on the CLI. Example: default-information
        # originate comes with a default metric-type of 2, which will enable the
        # entire default-information originate tree, even when not set via CLI so we
        # need to check this first and probably drop that key.
        if dict_search('default_information.originate', ospf) is None:
            del default_values['default_information']
        if 'mpls_te' not in ospf:
            del default_values['mpls_te']
        if 'graceful_restart' not in ospf:
            del default_values['graceful_restart']
        for area_num in default_values.get('area', []):
            if dict_search(f'area.{area_num}.area_type.nssa', ospf) is None:
                del default_values['area'][area_num]['area_type']['nssa']

        for protocol in ['babel', 'bgp', 'connected', 'isis', 'kernel', 'nhrp', 'rip', 'static']:
            if dict_search(f'redistribute.{protocol}', ospf) is None:
                del default_values['redistribute'][protocol]
        if not bool(default_values['redistribute']):
            del default_values['redistribute']

        for interface in ospf.get('interface', []):
            # We need to reload the defaults on every pass b/c of
            # hello-multiplier dependency on dead-interval
            # If hello-multiplier is set, we need to remove the default from
            # dead-interval.
            if 'hello_multiplier' in ospf['interface'][interface]:
                del default_values['interface'][interface]['dead_interval']

        ospf = config_dict_merge(default_values, ospf)
        return ospf

    def dict_helper_ospfv3_defaults(ospfv3, path):
        # We have gathered the dict representation of the CLI, but there are default
        # options which we need to update into the dictionary retrived.
        default_values = conf.get_config_defaults(path, key_mangling=('-', '_'),
                                                  get_first_key=True, recursive=True)

        # We have to cleanup the default dict, as default values could enable features
        # which are not explicitly enabled on the CLI. Example: default-information
        # originate comes with a default metric-type of 2, which will enable the
        # entire default-information originate tree, even when not set via CLI so we
        # need to check this first and probably drop that key.
        if dict_search('default_information.originate', ospfv3) is None:
            del default_values['default_information']
        if 'graceful_restart' not in ospfv3:
            del default_values['graceful_restart']

        for protocol in ['babel', 'bgp', 'connected', 'isis', 'kernel', 'ripng', 'static']:
            if dict_search(f'redistribute.{protocol}', ospfv3) is None:
                del default_values['redistribute'][protocol]
        if not bool(default_values['redistribute']):
            del default_values['redistribute']

        default_values.pop('interface', {})

        # merge in remaining default values
        ospfv3 = config_dict_merge(default_values, ospfv3)
        return ospfv3

    def dict_helper_pim_defaults(pim, path):
        # We have gathered the dict representation of the CLI, but there are default
        # options which we need to update into the dictionary retrived.
        default_values = conf.get_config_defaults(path, key_mangling=('-', '_'),
                                                  get_first_key=True, recursive=True)

        # We have to cleanup the default dict, as default values could enable features
        # which are not explicitly enabled on the CLI.
        for interface in pim.get('interface', []):
            if 'igmp' not in pim['interface'][interface]:
                del default_values['interface'][interface]['igmp']

        pim = config_dict_merge(default_values, pim)
        return pim

    def dict_helper_nhrp_defaults(nhrp):
        # NFLOG group numbers which are used in netfilter firewall rules and
        # in the global config in FRR.
        # https://docs.frrouting.org/en/latest/nhrpd.html#hub-functionality
        # https://docs.frrouting.org/en/latest/nhrpd.html#multicast-functionality
        # Use nflog group number for NHRP redirects = 1
        # Use nflog group number from MULTICAST traffic = 2
        nflog_redirect = 1
        nflog_multicast = 2

        nhrp = conf.merge_defaults(nhrp, recursive=True)

        nhrp_tunnel = conf.get_config_dict(['interfaces', 'tunnel'],
                                           key_mangling=('-', '_'),
                                           get_first_key=True,
                                           no_tag_node_value_mangle=True)

        if nhrp_tunnel: nhrp.update({'if_tunnel': nhrp_tunnel})

        for intf, intf_config in nhrp['tunnel'].items():
            if 'multicast' in intf_config:
                nhrp['multicast'] = nflog_multicast
            if 'redirect' in intf_config:
                nhrp['redirect'] = nflog_redirect

        ##Add ipsec profile config to nhrp configuration to apply encryption
        profile = conf.get_config_dict(['vpn', 'ipsec', 'profile'],
                                       key_mangling=('-', '_'),
                                       get_first_key=True,
                                       no_tag_node_value_mangle=True)

        for name, profile_conf in profile.items():
            if 'disable' in profile_conf:
                continue
            if 'bind' in profile_conf and 'tunnel' in profile_conf['bind']:
                interfaces = profile_conf['bind']['tunnel']
                if isinstance(interfaces, str):
                    interfaces = [interfaces]
                for interface in interfaces:
                    if dict_search(f'tunnel.{interface}', nhrp):
                        nhrp['tunnel'][interface][
                            'security_profile'] = name
        return nhrp

    # Ethernet and bonding interfaces can participate in EVPN which is configured via FRR
    tmp = {}
    for if_type in ['ethernet', 'bonding']:
        interface_path = ['interfaces', if_type]
        if not conf.exists(interface_path):
            continue
        for interface in conf.list_nodes(interface_path):
            evpn_path = interface_path + [interface, 'evpn']
            if not conf.exists(evpn_path):
                continue

            evpn = conf.get_config_dict(evpn_path, key_mangling=('-', '_'))
            tmp.update({interface : evpn})
    # At least one participating EVPN interface found, add to result dict
    if tmp: dict['interfaces'] = tmp

    # Zebra prefix exchange for Kernel IP/IPv6 and routing protocols
    for ip_version in ['ip', 'ipv6']:
        ip_cli_path = ['system', ip_version]
        ip_dict = conf.get_config_dict(ip_cli_path, key_mangling=('-', '_'),
                                        get_first_key=True, with_recursive_defaults=True)
        if ip_dict:
            ip_dict['afi'] = ip_version
            dict.update({ip_version : ip_dict})

    # Enable SNMP agentx support
    # SNMP AgentX support cannot be disabled once enabled
    if conf.exists(['service', 'snmp']):
        dict['snmp'] = {}

    # We will always need the policy key
    dict['policy'] = conf.get_config_dict(['policy'], key_mangling=('-', '_'),
                                          get_first_key=True,
                                          no_tag_node_value_mangle=True)

    # We need to check the CLI if the BABEL node is present and thus load in all the default
    # values present on the CLI - that's why we have if conf.exists()
    babel_cli_path = ['protocols', 'babel']
    if conf.exists(babel_cli_path):
        babel = conf.get_config_dict(babel_cli_path, key_mangling=('-', '_'),
                                     get_first_key=True,
                                     with_recursive_defaults=True)
        dict.update({'babel' : babel})

    # We need to check the CLI if the BFD node is present and thus load in all the default
    # values present on the CLI - that's why we have if conf.exists()
    bfd_cli_path = ['protocols', 'bfd']
    if conf.exists(bfd_cli_path):
        bfd = conf.get_config_dict(bfd_cli_path, key_mangling=('-', '_'),
                                   get_first_key=True,
                                   no_tag_node_value_mangle=True,
                                   with_recursive_defaults=True)
        dict.update({'bfd' : bfd})

    # We need to check the CLI if the BGP node is present and thus load in all the default
    # values present on the CLI - that's why we have if conf.exists()
    bgp_cli_path = ['protocols', 'bgp']
    if conf.exists(bgp_cli_path):
        bgp = conf.get_config_dict(bgp_cli_path, key_mangling=('-', '_'),
                                   get_first_key=True,
                                   no_tag_node_value_mangle=True,
                                   with_recursive_defaults=True)
        bgp['dependent_vrfs'] = {}
        dict.update({'bgp' : bgp})
    elif conf.exists_effective(bgp_cli_path):
        dict.update({'bgp' : {'deleted' : '', 'dependent_vrfs' : {}}})

    # We need to check the CLI if the EIGRP node is present and thus load in all the default
    # values present on the CLI - that's why we have if conf.exists()
    eigrp_cli_path = ['protocols', 'eigrp']
    if conf.exists(eigrp_cli_path):
        eigrp = conf.get_config_dict(eigrp_cli_path, key_mangling=('-', '_'),
                                     get_first_key=True,
                                     no_tag_node_value_mangle=True,
                                     with_recursive_defaults=True)
        dict.update({'eigrp' : eigrp})
    elif conf.exists_effective(eigrp_cli_path):
        dict.update({'eigrp' : {'deleted' : ''}})

    # We need to check the CLI if the ISIS node is present and thus load in all the default
    # values present on the CLI - that's why we have if conf.exists()
    isis_cli_path = ['protocols', 'isis']
    if conf.exists(isis_cli_path):
        isis = conf.get_config_dict(isis_cli_path, key_mangling=('-', '_'),
                                    get_first_key=True,
                                    no_tag_node_value_mangle=True,
                                    with_recursive_defaults=True)
        dict.update({'isis' : isis})
    elif conf.exists_effective(isis_cli_path):
        dict.update({'isis' : {'deleted' : ''}})

    # We need to check the CLI if the MPLS node is present and thus load in all the default
    # values present on the CLI - that's why we have if conf.exists()
    mpls_cli_path = ['protocols', 'mpls']
    if conf.exists(mpls_cli_path):
        mpls = conf.get_config_dict(mpls_cli_path, key_mangling=('-', '_'),
                                    get_first_key=True)
        dict.update({'mpls' : mpls})
    elif conf.exists_effective(mpls_cli_path):
        dict.update({'mpls' : {'deleted' : ''}})

    # We need to check the CLI if the OPENFABRIC node is present and thus load in all the default
    # values present on the CLI - that's why we have if conf.exists()
    openfabric_cli_path = ['protocols', 'openfabric']
    if conf.exists(openfabric_cli_path):
        openfabric = conf.get_config_dict(openfabric_cli_path, key_mangling=('-', '_'),
                                          get_first_key=True,
                                          no_tag_node_value_mangle=True)
        dict.update({'openfabric' : openfabric})
    elif conf.exists_effective(openfabric_cli_path):
        dict.update({'openfabric' : {'deleted' : ''}})

    # We need to check the CLI if the OSPF node is present and thus load in all the default
    # values present on the CLI - that's why we have if conf.exists()
    ospf_cli_path = ['protocols', 'ospf']
    if conf.exists(ospf_cli_path):
        ospf = conf.get_config_dict(ospf_cli_path, key_mangling=('-', '_'),
                                    get_first_key=True)
        ospf = dict_helper_ospf_defaults(ospf, ospf_cli_path)
        dict.update({'ospf' : ospf})
    elif conf.exists_effective(ospf_cli_path):
        dict.update({'ospf' : {'deleted' : ''}})

    # We need to check the CLI if the OSPFv3 node is present and thus load in all the default
    # values present on the CLI - that's why we have if conf.exists()
    ospfv3_cli_path = ['protocols', 'ospfv3']
    if conf.exists(ospfv3_cli_path):
        ospfv3 = conf.get_config_dict(ospfv3_cli_path, key_mangling=('-', '_'),
                                      get_first_key=True)
        ospfv3 = dict_helper_ospfv3_defaults(ospfv3, ospfv3_cli_path)
        dict.update({'ospfv3' : ospfv3})
    elif conf.exists_effective(ospfv3_cli_path):
        dict.update({'ospfv3' : {'deleted' : ''}})

    # We need to check the CLI if the PIM node is present and thus load in all the default
    # values present on the CLI - that's why we have if conf.exists()
    pim_cli_path = ['protocols', 'pim']
    if conf.exists(pim_cli_path):
        pim = conf.get_config_dict(pim_cli_path, key_mangling=('-', '_'),
                                   get_first_key=True)
        pim = dict_helper_pim_defaults(pim, pim_cli_path)
        dict.update({'pim' : pim})
    elif conf.exists_effective(pim_cli_path):
        dict.update({'pim' : {'deleted' : ''}})

    # We need to check the CLI if the PIM6 node is present and thus load in all the default
    # values present on the CLI - that's why we have if conf.exists()
    pim6_cli_path = ['protocols', 'pim6']
    if conf.exists(pim6_cli_path):
        pim6 = conf.get_config_dict(pim6_cli_path, key_mangling=('-', '_'),
                                    get_first_key=True,
                                    with_recursive_defaults=True)
        dict.update({'pim6' : pim6})
    elif conf.exists_effective(pim6_cli_path):
        dict.update({'pim6' : {'deleted' : ''}})

    # We need to check the CLI if the RIP node is present and thus load in all the default
    # values present on the CLI - that's why we have if conf.exists()
    rip_cli_path = ['protocols', 'rip']
    if conf.exists(rip_cli_path):
        rip = conf.get_config_dict(rip_cli_path, key_mangling=('-', '_'),
                                   get_first_key=True,
                                   with_recursive_defaults=True)
        dict.update({'rip' : rip})
    elif conf.exists_effective(rip_cli_path):
        dict.update({'rip' : {'deleted' : ''}})

    # We need to check the CLI if the RIPng node is present and thus load in all the default
    # values present on the CLI - that's why we have if conf.exists()
    ripng_cli_path = ['protocols', 'ripng']
    if conf.exists(ripng_cli_path):
        ripng = conf.get_config_dict(ripng_cli_path, key_mangling=('-', '_'),
                                     get_first_key=True,
                                     with_recursive_defaults=True)
        dict.update({'ripng' : ripng})
    elif conf.exists_effective(ripng_cli_path):
        dict.update({'ripng' : {'deleted' : ''}})

    # We need to check the CLI if the RPKI node is present and thus load in all the default
    # values present on the CLI - that's why we have if conf.exists()
    rpki_cli_path = ['protocols', 'rpki']
    if conf.exists(rpki_cli_path):
        rpki = conf.get_config_dict(rpki_cli_path, key_mangling=('-', '_'),
                                     get_first_key=True, with_pki=True,
                                     with_recursive_defaults=True)
        rpki_ssh_key_base = '/run/frr/id_rpki'
        for cache, cache_config in rpki.get('cache',{}).items():
            if 'ssh' in cache_config:
                cache_config['ssh']['public_key_file'] = f'{rpki_ssh_key_base}_{cache}.pub'
                cache_config['ssh']['private_key_file'] = f'{rpki_ssh_key_base}_{cache}'
        dict.update({'rpki' : rpki})
    elif conf.exists_effective(rpki_cli_path):
        dict.update({'rpki' : {'deleted' : ''}})

    # We need to check the CLI if the Segment Routing node is present and thus load in
    # all the default values present on the CLI - that's why we have if conf.exists()
    sr_cli_path = ['protocols', 'segment-routing']
    if conf.exists(sr_cli_path):
        sr = conf.get_config_dict(sr_cli_path, key_mangling=('-', '_'),
                                  get_first_key=True,
                                  no_tag_node_value_mangle=True,
                                  with_recursive_defaults=True)
        dict.update({'segment_routing' : sr})
    elif conf.exists_effective(sr_cli_path):
        dict.update({'segment_routing' : {'deleted' : ''}})

    # We need to check the CLI if the static node is present and thus load in
    # all the default values present on the CLI - that's why we have if conf.exists()
    static_cli_path = ['protocols', 'static']
    if conf.exists(static_cli_path):
        static = conf.get_config_dict(static_cli_path, key_mangling=('-', '_'),
                                  get_first_key=True,
                                  no_tag_node_value_mangle=True)
        dict.update({'static' : static})
    elif conf.exists_effective(static_cli_path):
        dict.update({'static' : {'deleted' : ''}})

    # We need to check the CLI if the NHRP node is present and thus load in all the default
    # values present on the CLI - that's why we have if conf.exists()
    nhrp_cli_path = ['protocols', 'nhrp']
    if conf.exists(nhrp_cli_path):
        nhrp = conf.get_config_dict(nhrp_cli_path, key_mangling=('-', '_'),
                                    get_first_key=True,
                                    no_tag_node_value_mangle=True)
        nhrp = dict_helper_nhrp_defaults(nhrp)
        dict.update({'nhrp' : nhrp})
    elif conf.exists_effective(nhrp_cli_path):
        dict.update({'nhrp' : {'deleted' : ''}})

    # T3680 - get a list of all interfaces currently configured to use DHCP
    tmp = get_dhcp_interfaces(conf)
    if tmp:
        if 'static' in dict:
            dict['static'].update({'dhcp' : tmp})
        else:
            dict.update({'static' : {'dhcp' : tmp}})
    tmp = get_pppoe_interfaces(conf)
    if tmp:
        if 'static' in dict:
            dict['static'].update({'pppoe' : tmp})
        else:
            dict.update({'static' : {'pppoe' : tmp}})

    # keep a re-usable list of dependent VRFs
    dependent_vrfs_default = {}
    if 'bgp' in dict:
        dependent_vrfs_default = deepcopy(dict['bgp'])
        # we do not need to nest the 'dependent_vrfs' key - simply remove it
        if 'dependent_vrfs' in dependent_vrfs_default:
            del dependent_vrfs_default['dependent_vrfs']

    vrf_cli_path = ['vrf', 'name']
    if conf.exists(vrf_cli_path):
        vrf = conf.get_config_dict(vrf_cli_path, key_mangling=('-', '_'),
                                   get_first_key=False,
                                   no_tag_node_value_mangle=True)
        # We do not have any VRF related default values on the CLI. The defaults will only
        # come into place under the protocols tree, thus we can safely merge them with the
        # appropriate routing protocols
        for vrf_name, vrf_config in vrf['name'].items():
            bgp_vrf_path = ['vrf', 'name', vrf_name, 'protocols', 'bgp']
            if 'bgp' in vrf_config.get('protocols', []):
                # We have gathered the dict representation of the CLI, but there are default
                # options which we need to update into the dictionary retrived.
                default_values = conf.get_config_defaults(bgp_vrf_path, key_mangling=('-', '_'),
                                                        get_first_key=True, recursive=True)

                # merge in remaining default values
                vrf_config['protocols']['bgp'] = config_dict_merge(default_values,
                                                                   vrf_config['protocols']['bgp'])

                # Add this BGP VRF instance as dependency into the default VRF
                if 'bgp' in dict:
                    dict['bgp']['dependent_vrfs'].update({vrf_name : deepcopy(vrf_config)})

                vrf_config['protocols']['bgp']['dependent_vrfs'] = conf.get_config_dict(
                    vrf_cli_path, key_mangling=('-', '_'), get_first_key=True,
                    no_tag_node_value_mangle=True)

                # We can safely delete ourself from the dependent VRF list
                if vrf_name in vrf_config['protocols']['bgp']['dependent_vrfs']:
                    del vrf_config['protocols']['bgp']['dependent_vrfs'][vrf_name]

                # Add dependency on possible existing default VRF to this VRF
                if 'bgp' in dict:
                    vrf_config['protocols']['bgp']['dependent_vrfs'].update({'default': {'protocols': {
                        'bgp': dependent_vrfs_default}}})
            elif conf.exists_effective(bgp_vrf_path):
                # Add this BGP VRF instance as dependency into the default VRF
                tmp = {'deleted' : '', 'dependent_vrfs': deepcopy(vrf['name'])}
                # We can safely delete ourself from the dependent VRF list
                if vrf_name in tmp['dependent_vrfs']:
                    del tmp['dependent_vrfs'][vrf_name]

                # Add dependency on possible existing default VRF to this VRF
                if 'bgp' in dict:
                    tmp['dependent_vrfs'].update({'default': {'protocols': {
                        'bgp': dependent_vrfs_default}}})

                if 'bgp' in dict:
                    dict['bgp']['dependent_vrfs'].update({vrf_name : {'protocols': tmp} })

                if 'protocols' not in vrf['name'][vrf_name]:
                    vrf['name'][vrf_name].update({'protocols': {'bgp' : tmp}})
                else:
                    vrf['name'][vrf_name]['protocols'].update({'bgp' : tmp})

            # We need to check the CLI if the EIGRP node is present and thus load in all the default
            # values present on the CLI - that's why we have if conf.exists()
            eigrp_vrf_path = ['vrf', 'name', vrf_name, 'protocols', 'eigrp']
            if 'eigrp' in vrf_config.get('protocols', []):
                eigrp = conf.get_config_dict(eigrp_vrf_path, key_mangling=('-', '_'), get_first_key=True,
                                            no_tag_node_value_mangle=True)
                vrf['name'][vrf_name]['protocols'].update({'eigrp' : isis})
            elif conf.exists_effective(eigrp_vrf_path):
                vrf['name'][vrf_name]['protocols'].update({'eigrp' : {'deleted' : ''}})

            # We need to check the CLI if the ISIS node is present and thus load in all the default
            # values present on the CLI - that's why we have if conf.exists()
            isis_vrf_path = ['vrf', 'name', vrf_name, 'protocols', 'isis']
            if 'isis' in vrf_config.get('protocols', []):
                isis = conf.get_config_dict(isis_vrf_path, key_mangling=('-', '_'), get_first_key=True,
                                            no_tag_node_value_mangle=True, with_recursive_defaults=True)
                vrf['name'][vrf_name]['protocols'].update({'isis' : isis})
            elif conf.exists_effective(isis_vrf_path):
                vrf['name'][vrf_name]['protocols'].update({'isis' : {'deleted' : ''}})

            # We need to check the CLI if the OSPF node is present and thus load in all the default
            # values present on the CLI - that's why we have if conf.exists()
            ospf_vrf_path = ['vrf', 'name', vrf_name, 'protocols', 'ospf']
            if 'ospf' in vrf_config.get('protocols', []):
                ospf = conf.get_config_dict(ospf_vrf_path, key_mangling=('-', '_'), get_first_key=True)
                ospf = dict_helper_ospf_defaults(vrf_config['protocols']['ospf'], ospf_vrf_path)
                vrf['name'][vrf_name]['protocols'].update({'ospf' : ospf})
            elif conf.exists_effective(ospf_vrf_path):
                vrf['name'][vrf_name]['protocols'].update({'ospf' : {'deleted' : ''}})

            # We need to check the CLI if the OSPFv3 node is present and thus load in all the default
            # values present on the CLI - that's why we have if conf.exists()
            ospfv3_vrf_path = ['vrf', 'name', vrf_name, 'protocols', 'ospfv3']
            if 'ospfv3' in vrf_config.get('protocols', []):
                ospfv3 = conf.get_config_dict(ospfv3_vrf_path, key_mangling=('-', '_'), get_first_key=True)
                ospfv3 = dict_helper_ospfv3_defaults(vrf_config['protocols']['ospfv3'], ospfv3_vrf_path)
                vrf['name'][vrf_name]['protocols'].update({'ospfv3' : ospfv3})
            elif conf.exists_effective(ospfv3_vrf_path):
                vrf['name'][vrf_name]['protocols'].update({'ospfv3' : {'deleted' : ''}})

            # We need to check the CLI if the RPKI node is present and thus load in all the default
            # values present on the CLI - that's why we have if conf.exists()
            rpki_vrf_path = ['vrf', 'name', vrf_name, 'protocols', 'rpki']
            if 'rpki' in vrf_config.get('protocols', []):
                rpki = conf.get_config_dict(rpki_vrf_path, key_mangling=('-', '_'), get_first_key=True,
                                            with_pki=True, with_recursive_defaults=True)
                rpki_ssh_key_base = '/run/frr/id_rpki'
                for cache, cache_config in rpki.get('cache',{}).items():
                    if 'ssh' in cache_config:
                        cache_config['ssh']['public_key_file'] = f'{rpki_ssh_key_base}_{cache}.pub'
                        cache_config['ssh']['private_key_file'] = f'{rpki_ssh_key_base}_{cache}'
                vrf['name'][vrf_name]['protocols'].update({'rpki' : rpki})
            elif conf.exists_effective(rpki_vrf_path):
                vrf['name'][vrf_name]['protocols'].update({'rpki' : {'deleted' : ''}})

            # We need to check the CLI if the static node is present and thus load in all the default
            # values present on the CLI - that's why we have if conf.exists()
            static_vrf_path = ['vrf', 'name', vrf_name, 'protocols', 'static']
            if 'static' in vrf_config.get('protocols', []):
                static = conf.get_config_dict(static_vrf_path, key_mangling=('-', '_'),
                                              get_first_key=True,
                                              no_tag_node_value_mangle=True)
                # T3680 - get a list of all interfaces currently configured to use DHCP
                tmp = get_dhcp_interfaces(conf, vrf_name)
                if tmp: static.update({'dhcp' : tmp})
                tmp = get_pppoe_interfaces(conf, vrf_name)
                if tmp: static.update({'pppoe' : tmp})

                vrf['name'][vrf_name]['protocols'].update({'static': static})
            elif conf.exists_effective(static_vrf_path):
                vrf['name'][vrf_name]['protocols'].update({'static': {'deleted' : ''}})

            vrf_vni_path = ['vrf', 'name', vrf_name, 'vni']
            if conf.exists(vrf_vni_path):
                vrf_config.update({'vni': conf.return_value(vrf_vni_path)})

            dict.update({'vrf' : vrf})
    elif conf.exists_effective(vrf_cli_path):
        effective_vrf = conf.get_config_dict(vrf_cli_path, key_mangling=('-', '_'),
                                             get_first_key=False,
                                             no_tag_node_value_mangle=True,
                                             effective=True)
        vrf = {'name' : {}}
        for vrf_name, vrf_config in effective_vrf.get('name', {}).items():
            vrf['name'].update({vrf_name : {}})
            for protocol in frr_protocols:
                if protocol in vrf_config.get('protocols', []):
                    # Create initial protocols key if not present
                    if 'protocols' not in vrf['name'][vrf_name]:
                        vrf['name'][vrf_name].update({'protocols' : {}})
                    # All routing protocols are deleted when we pass this point
                    tmp = {'deleted' : ''}

                    # Special treatment for BGP routing protocol
                    if protocol == 'bgp':
                        tmp['dependent_vrfs'] = {}
                        if 'name' in vrf:
                            tmp['dependent_vrfs'] = conf.get_config_dict(
                                vrf_cli_path, key_mangling=('-', '_'),
                                get_first_key=True, no_tag_node_value_mangle=True,
                                effective=True)
                        # Add dependency on possible existing default VRF to this VRF
                        if 'bgp' in dict:
                            tmp['dependent_vrfs'].update({'default': {'protocols': {
                                'bgp': dependent_vrfs_default}}})
                        # We can safely delete ourself from the dependent VRF list
                        if vrf_name in tmp['dependent_vrfs']:
                            del tmp['dependent_vrfs'][vrf_name]

                    # Update VRF related dict
                    vrf['name'][vrf_name]['protocols'].update({protocol : tmp})

        dict.update({'vrf' : vrf})

    if os.path.exists(frr_debug_enable):
        print(f'---- get_frrender_dict({conf}) ----')
        import pprint
        pprint.pprint(dict)
        print('-----------------------------------')

    return dict

class FRRender:
    cached_config_dict = {}
    def __init__(self):
        self._frr_conf = '/run/frr/config/vyos.frr.conf'

    def generate(self, config_dict) -> None:
        """
        Generate FRR configuration file
        Returns False if no changes to configuration were made, otherwise True
        """
        if not isinstance(config_dict, dict):
            tmp = type(config_dict)
            raise ValueError(f'Config must be of type "dict" and not "{tmp}"!')


        if self.cached_config_dict == config_dict:
            debug('FRR:        NO CHANGES DETECTED')
            return False
        self.cached_config_dict = config_dict

        def inline_helper(config_dict) -> str:
            output = '!\n'
            if 'babel' in config_dict and 'deleted' not in config_dict['babel']:
                output += render_to_string('frr/babeld.frr.j2', config_dict['babel'])
                output += '\n'
            if 'bfd' in config_dict and 'deleted' not in config_dict['bfd']:
                output += render_to_string('frr/bfdd.frr.j2', config_dict['bfd'])
                output += '\n'
            if 'bgp' in config_dict and 'deleted' not in config_dict['bgp']:
                output += render_to_string('frr/bgpd.frr.j2', config_dict['bgp'])
                output += '\n'
            if 'eigrp' in config_dict and 'deleted' not in config_dict['eigrp']:
                output += render_to_string('frr/eigrpd.frr.j2', config_dict['eigrp'])
                output += '\n'
            if 'isis' in config_dict and 'deleted' not in config_dict['isis']:
                output += render_to_string('frr/isisd.frr.j2', config_dict['isis'])
                output += '\n'
            if 'mpls' in config_dict and 'deleted' not in config_dict['mpls']:
                output += render_to_string('frr/ldpd.frr.j2', config_dict['mpls'])
                output += '\n'
            if 'openfabric' in config_dict and 'deleted' not in config_dict['openfabric']:
                output += render_to_string('frr/fabricd.frr.j2', config_dict['openfabric'])
                output += '\n'
            if 'ospf' in config_dict and 'deleted' not in config_dict['ospf']:
                output += render_to_string('frr/ospfd.frr.j2', config_dict['ospf'])
                output += '\n'
            if 'ospfv3' in config_dict and 'deleted' not in config_dict['ospfv3']:
                output += render_to_string('frr/ospf6d.frr.j2', config_dict['ospfv3'])
                output += '\n'
            if 'pim' in config_dict and 'deleted' not in config_dict['pim']:
                output += render_to_string('frr/pimd.frr.j2', config_dict['pim'])
                output += '\n'
            if 'pim6' in config_dict and 'deleted' not in config_dict['pim6']:
                output += render_to_string('frr/pim6d.frr.j2', config_dict['pim6'])
                output += '\n'
            if 'policy' in config_dict and len(config_dict['policy']) > 0:
                output += render_to_string('frr/policy.frr.j2', config_dict['policy'])
                output += '\n'
            if 'rip' in config_dict and 'deleted' not in config_dict['rip']:
                output += render_to_string('frr/ripd.frr.j2', config_dict['rip'])
                output += '\n'
            if 'ripng' in config_dict and 'deleted' not in config_dict['ripng']:
                output += render_to_string('frr/ripngd.frr.j2', config_dict['ripng'])
                output += '\n'
            if 'rpki' in config_dict and 'deleted' not in config_dict['rpki']:
                output += render_to_string('frr/rpki.frr.j2', {'rpki': config_dict['rpki']})
                output += '\n'
            if 'segment_routing' in config_dict and 'deleted' not in config_dict['segment_routing']:
                output += render_to_string('frr/zebra.segment_routing.frr.j2', config_dict['segment_routing'])
                output += '\n'
            if 'static' in config_dict and 'deleted' not in config_dict['static']:
                output += render_to_string('frr/staticd.frr.j2', config_dict['static'])
                output += '\n'
            if 'ip' in config_dict and 'deleted' not in config_dict['ip']:
                output += render_to_string('frr/zebra.route-map.frr.j2', config_dict['ip'])
                output += '\n'
            if 'ipv6' in config_dict and 'deleted' not in config_dict['ipv6']:
                output += render_to_string('frr/zebra.route-map.frr.j2', config_dict['ipv6'])
                output += '\n'
            if 'nhrp' in config_dict and 'deleted' not in config_dict['nhrp']:
                output += render_to_string('frr/nhrpd.frr.j2', config_dict['nhrp'])
                output += '\n'
            return output

        debug('FRR:        START CONFIGURATION RENDERING')
        # we can not reload an empty file, thus we always embed the marker
        output = '!\n'
        # Enable FRR logging
        output += 'log syslog\n'
        output += 'log facility local7\n'
        # Enable SNMP agentx support
        # SNMP AgentX support cannot be disabled once enabled
        if 'snmp' in config_dict:
            output += 'agentx\n'
        # Add routing protocols in global VRF
        output += inline_helper(config_dict)
        # Interface configuration for EVPN is not VRF related
        if 'interfaces' in config_dict:
            output += render_to_string('frr/evpn.mh.frr.j2', {'interfaces' : config_dict['interfaces']})
            output += '\n'

        if 'vrf' in config_dict and 'name' in config_dict['vrf']:
            output += render_to_string('frr/zebra.vrf.route-map.frr.j2', config_dict['vrf'])
            for vrf, vrf_config in config_dict['vrf']['name'].items():
                if 'protocols' not in vrf_config:
                    continue
                for protocol in vrf_config['protocols']:
                    vrf_config['protocols'][protocol]['vrf'] = vrf

                output += inline_helper(vrf_config['protocols'])

        # remove any accidently added empty newline to not confuse FRR
        output = os.linesep.join([s for s in output.splitlines() if s])

        if '!!' in output:
            raise ConfigError('FRR configuration contains "!!" which is not allowed')

        debug(output)
        write_file(self._frr_conf, output)
        debug('FRR:        RENDERING CONFIG COMPLETE')
        return True

    def apply(self, count_max=5):
        count = 0
        emsg = ''
        while count < count_max:
            count += 1
            debug(f'FRR: reloading configuration - tries: {count} | Python class ID: {id(self)}')
            cmdline = '/usr/lib/frr/frr-reload.py --reload'
            if os.path.exists(frr_debug_enable):
                cmdline += ' --debug --stdout'
            rc, emsg = rc_cmd(f'{cmdline} {self._frr_conf}')
            if rc != 0:
                sleep(2)
                continue
            debug(emsg)
            debug('FRR: configuration reload complete')
            break

        if count >= count_max:
            raise ConfigError(emsg)

        # T3217: Save FRR configuration to /run/frr/config/frr.conf
        return cmd('/usr/bin/vtysh -n --writeconfig')
