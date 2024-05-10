#!/usr/bin/env python3
#
# Copyright (C) 2019-2024 VyOS maintainers and contributors
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
from vyos.configdict import get_interface_dict
from vyos.configdict import is_node_changed
from vyos.configdict import leaf_node_changed
from vyos.configdict import is_member
from vyos.configdict import is_source_interface
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_dhcpv6
from vyos.configverify import verify_mirror_redirect
from vyos.configverify import verify_mtu_ipv6
from vyos.configverify import verify_vlan_config
from vyos.configverify import verify_vrf
from vyos.ifconfig import BondIf
from vyos.ifconfig.ethernet import EthernetIf
from vyos.ifconfig import Section
from vyos.template import render_to_string
from vyos.utils.assertion import assert_mac
from vyos.utils.dict import dict_search
from vyos.utils.dict import dict_to_paths_values
from vyos.utils.network import interface_exists
from vyos.configdict import has_address_configured
from vyos.configdict import has_vrf_configured
from vyos.configdep import set_dependents, call_dependents
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

def get_bond_mode(mode):
    if mode == 'round-robin':
        return 'balance-rr'
    elif mode == 'active-backup':
        return 'active-backup'
    elif mode == 'xor-hash':
        return 'balance-xor'
    elif mode == 'broadcast':
        return 'broadcast'
    elif mode == '802.3ad':
        return '802.3ad'
    elif mode == 'transmit-load-balance':
        return 'balance-tlb'
    elif mode == 'adaptive-load-balance':
        return 'balance-alb'
    else:
        raise ConfigError(f'invalid bond mode "{mode}"')

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'bonding']
    ifname, bond = get_interface_dict(conf, base)

    # To make our own life easier transfor the list of member interfaces
    # into a dictionary - we will use this to add additional information
    # later on for each member
    if 'member' in bond and 'interface' in bond['member']:
        # convert list of member interfaces to a dictionary
        bond['member']['interface'] = {k: {} for k in bond['member']['interface']}

    if 'mode' in bond:
        bond['mode'] = get_bond_mode(bond['mode'])

    tmp = is_node_changed(conf, base + [ifname, 'mode'])
    if tmp: bond['shutdown_required'] = {}

    tmp = is_node_changed(conf, base + [ifname, 'lacp-rate'])
    if tmp: bond['shutdown_required'] = {}

    # determine which members have been removed
    interfaces_removed = leaf_node_changed(conf, base + [ifname, 'member', 'interface'])
    # Reset config level to interfaces
    old_level = conf.get_level()
    conf.set_level(['interfaces'])

    if interfaces_removed:
        bond['shutdown_required'] = {}
        if 'member' not in bond:
            bond['member'] = {}

        tmp = {}
        for interface in interfaces_removed:
            # if member is deleted from bond, add dependencies to call
            # ethernet commit again in apply function
            # to apply options under ethernet section
            set_dependents('ethernet', conf, interface)
            section = Section.section(interface) # this will be 'ethernet' for 'eth0'
            if conf.exists([section, interface, 'disable']):
                tmp[interface] = {'disable': ''}
            else:
                tmp[interface] = {}

        # also present the interfaces to be removed from the bond as dictionary
        bond['member']['interface_remove'] = tmp

    # Restore existing config level
    conf.set_level(old_level)

    if dict_search('member.interface', bond):
        for interface, interface_config in bond['member']['interface'].items():

            interface_ethernet_config = conf.get_config_dict(
                ['interfaces', 'ethernet', interface],
                key_mangling=('-', '_'),
                get_first_key=True,
                no_tag_node_value_mangle=True,
                with_defaults=False,
                with_recursive_defaults=False)

            interface_config['config_paths'] = dict_to_paths_values(interface_ethernet_config)

            # Check if member interface is a new member
            if not conf.exists_effective(base + [ifname, 'member', 'interface', interface]):
                bond['shutdown_required'] = {}
                interface_config['new_added'] = {}

            # Check if member interface is disabled
            conf.set_level(['interfaces'])

            section = Section.section(interface) # this will be 'ethernet' for 'eth0'
            if conf.exists([section, interface, 'disable']):
                interface_config['disable'] = ''

            conf.set_level(old_level)

            # Check if member interface is already member of another bridge
            tmp = is_member(conf, interface, 'bridge')
            if tmp: interface_config['is_bridge_member'] = tmp

            # Check if member interface is already member of a bond
            tmp = is_member(conf, interface, 'bonding')
            for tmp in is_member(conf, interface, 'bonding'):
                if bond['ifname'] == tmp:
                    continue
                interface_config['is_bond_member'] = tmp

            # Check if member interface is used as source-interface on another interface
            tmp = is_source_interface(conf, interface)
            if tmp: interface_config['is_source_interface'] = tmp

            # bond members must not have an assigned address
            tmp = has_address_configured(conf, interface)
            if tmp: interface_config['has_address'] = {}

            # bond members must not have a VRF attached
            tmp = has_vrf_configured(conf, interface)
            if tmp: interface_config['has_vrf'] = {}
    return bond


def verify(bond):
    if 'deleted' in bond:
        verify_bridge_delete(bond)
        return None

    if 'arp_monitor' in bond:
        if 'target' in bond['arp_monitor'] and len(bond['arp_monitor']['target']) > 16:
            raise ConfigError('The maximum number of arp-monitor targets is 16')

        if 'interval' in bond['arp_monitor'] and int(bond['arp_monitor']['interval']) > 0:
            if bond['mode'] in ['802.3ad', 'balance-tlb', 'balance-alb']:
                raise ConfigError('ARP link monitoring does not work for mode 802.3ad, ' \
                                  'transmit-load-balance or adaptive-load-balance')

    if 'primary' in bond:
        if bond['mode'] not in ['active-backup', 'balance-tlb', 'balance-alb']:
            raise ConfigError('Option primary - mode dependency failed, not'
                              'supported in mode {mode}!'.format(**bond))

    verify_mtu_ipv6(bond)
    verify_address(bond)
    verify_dhcpv6(bond)
    verify_vrf(bond)
    verify_mirror_redirect(bond)

    # use common function to verify VLAN configuration
    verify_vlan_config(bond)

    bond_name = bond['ifname']
    if dict_search('member.interface', bond):
        for interface, interface_config in bond['member']['interface'].items():
            error_msg = f'Can not add interface "{interface}" to bond, '

            if interface == 'lo':
                raise ConfigError('Loopback interface "lo" can not be added to a bond')

            if not interface_exists(interface):
                raise ConfigError(error_msg + 'it does not exist!')

            if 'is_bridge_member' in interface_config:
                tmp = next(iter(interface_config['is_bridge_member']))
                raise ConfigError(error_msg + f'it is already a member of bridge "{tmp}"!')

            if 'is_bond_member' in interface_config:
                tmp = next(iter(interface_config['is_bond_member']))
                raise ConfigError(error_msg + f'it is already a member of bond "{tmp}"!')

            if 'is_source_interface' in interface_config:
                tmp = interface_config['is_source_interface']
                raise ConfigError(error_msg + f'it is the source-interface of "{tmp}"!')

            if 'has_address' in interface_config:
                raise ConfigError(error_msg + 'it has an address assigned!')

            if 'has_vrf' in interface_config:
                raise ConfigError(error_msg + 'it has a VRF assigned!')

            if 'new_added' in interface_config and 'config_paths' in interface_config:
                for option_path, option_value in interface_config['config_paths'].items():
                    if option_path in EthernetIf.get_bond_member_allowed_options() :
                        continue
                    if option_path in BondIf.get_inherit_bond_options():
                        continue
                    raise ConfigError(error_msg + f'it has a "{option_path.replace(".", " ")}" assigned!')

    if 'primary' in bond:
        if bond['primary'] not in bond['member']['interface']:
            raise ConfigError(f'Primary interface of bond "{bond_name}" must be a member interface')

        if bond['mode'] not in ['active-backup', 'balance-tlb', 'balance-alb']:
            raise ConfigError('primary interface only works for mode active-backup, ' \
                              'transmit-load-balance or adaptive-load-balance')

    if 'system_mac' in bond:
        if bond['mode'] != '802.3ad':
            raise ConfigError('Actor MAC address only available in 802.3ad mode!')

        system_mac = bond['system_mac']
        try:
            assert_mac(system_mac, test_all_zero=False)
        except:
            raise ConfigError(f'Cannot use a multicast MAC address "{system_mac}" as system-mac!')

    return None

def generate(bond):
    bond['frr_zebra_config'] = ''
    if 'deleted' not in bond:
        bond['frr_zebra_config'] = render_to_string('frr/evpn.mh.frr.j2', bond)
    return None

def apply(bond):
    ifname = bond['ifname']
    b = BondIf(ifname)
    if 'deleted' in bond:
        # delete interface
        b.remove()
    else:
        b.update(bond)

    if dict_search('member.interface_remove', bond):
        try:
            call_dependents()
        except ConfigError:
            raise ConfigError('Error in updating ethernet interface '
                              'after deleting it from bond')

    zebra_daemon = 'zebra'
    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()

    # The route-map used for the FIB (zebra) is part of the zebra daemon
    frr_cfg.load_configuration(zebra_daemon)
    frr_cfg.modify_section(f'^interface {ifname}', stop_pattern='^exit', remove_stop_mark=True)
    if 'frr_zebra_config' in bond:
        frr_cfg.add_before(frr.default_add_before, bond['frr_zebra_config'])
    frr_cfg.commit_configuration(zebra_daemon)

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
