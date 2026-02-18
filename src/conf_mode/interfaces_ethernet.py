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
import re

from sys import exit

from vyos.base import Warning
from vyos.config import Config
from vyos.configdep import set_dependents
from vyos.configdep import call_dependents
from vyos.configdict import get_interface_dict
from vyos.configdict import is_node_changed
from vyos.configdict import get_flowtable_interfaces
from vyos.configverify import verify_address
from vyos.configverify import verify_dhcpv6
from vyos.configverify import verify_interface_exists
from vyos.configverify import verify_mirror_redirect
from vyos.configverify import verify_mtu
from vyos.configverify import verify_mtu_ipv6
from vyos.configverify import verify_vlan_config
from vyos.configverify import verify_vrf
from vyos.configverify import verify_bond_bridge_member
from vyos.configverify import verify_eapol
from vyos.ethtool import Ethtool
from vyos.netlink import coalesce
from vyos.frrender import FRRender
from vyos.frrender import get_frrender_dict
from vyos.ifconfig import EthernetIf
from vyos.ifconfig import BondIf
from vyos.utils.dict import dict_search
from vyos.utils.dict import dict_to_paths_values
from vyos.utils.dict import dict_set
from vyos.utils.dict import dict_delete
from vyos.utils.process import is_systemd_service_running
from vyos.vpp.control_vpp import VPPControl
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def update_bond_options(conf: Config, eth_conf: dict) -> list:
    """
    Return list of blocked options if interface is a bond member
    :param conf: Config object
    :type conf: Config
    :param eth_conf: Ethernet config dictionary
    :type eth_conf: dict
    :return: List of blocked options
    :rtype: list
    """
    blocked_list = []
    bond_name = list(eth_conf['is_bond_member'].keys())[0]
    config_without_defaults = conf.get_config_dict(
        ['interfaces', 'ethernet', eth_conf['ifname']],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_defaults=False,
        with_recursive_defaults=False)
    config_with_defaults = conf.get_config_dict(
        ['interfaces', 'ethernet', eth_conf['ifname']],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_defaults=True,
        with_recursive_defaults=True)
    bond_config_with_defaults = conf.get_config_dict(
        ['interfaces', 'bonding', bond_name],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_defaults=True,
        with_recursive_defaults=True)
    eth_dict_paths = dict_to_paths_values(config_without_defaults)
    eth_path_base = ['interfaces', 'ethernet', eth_conf['ifname']]

    #if option is configured under ethernet section
    for option_path, option_value in eth_dict_paths.items():
        bond_option_value = dict_search(option_path, bond_config_with_defaults)

        #If option is allowed for changing then continue
        if option_path in EthernetIf.get_bond_member_allowed_options():
            continue
        # if option is inherited from bond then set valued from bond interface
        if option_path in BondIf.get_inherit_bond_options():
            # If option equals to bond option then do nothing
            if option_value == bond_option_value:
                continue
            else:
                # if ethernet has option and bond interface has
                # then copy it from bond
                if bond_option_value is not None:
                    if is_node_changed(conf, eth_path_base + option_path.split('.')):
                        Warning(
                            f'Cannot apply "{option_path.replace(".", " ")}" to "{option_value}".' \
                            f' Interface "{eth_conf["ifname"]}" is a bond member.' \
                            f' Option is inherited from bond "{bond_name}"')
                    dict_set(option_path, bond_option_value, eth_conf)
                    continue
                # if ethernet has option and bond interface does not have
                # then delete it form dict and do not apply it
                else:
                    if is_node_changed(conf, eth_path_base + option_path.split('.')):
                        Warning(
                            f'Cannot apply "{option_path.replace(".", " ")}".' \
                            f' Interface "{eth_conf["ifname"]}" is a bond member.' \
                            f' Option is inherited from bond "{bond_name}"')
                    dict_delete(option_path, eth_conf)
        blocked_list.append(option_path)

    # if inherited option is not configured under ethernet section but configured under bond section
    for option_path in BondIf.get_inherit_bond_options():
        bond_option_value = dict_search(option_path, bond_config_with_defaults)
        if bond_option_value is not None:
            if option_path not in eth_dict_paths:
                if is_node_changed(conf, eth_path_base + option_path.split('.')):
                    Warning(
                        f'Cannot apply "{option_path.replace(".", " ")}" to "{dict_search(option_path, config_with_defaults)}".' \
                        f' Interface "{eth_conf["ifname"]}" is a bond member. ' \
                        f'Option is inherited from bond "{bond_name}"')
                dict_set(option_path, bond_option_value, eth_conf)
    eth_conf['bond_blocked_changes'] = blocked_list
    return None

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()

    base = ['interfaces', 'ethernet']
    ifname, ethernet = get_interface_dict(conf, base, with_pki=True)

    # T5862 - default MTU is not acceptable in some environments
    # There are cloud environments available where the maximum supported
    # ethernet MTU is e.g. 1450 bytes, thus we clamp this to the adapters
    # maximum MTU value or 1500 bytes - whatever is lower
    if 'mtu' not in ethernet:
        try:
            ethernet['mtu'] = '1500'
            max_mtu = EthernetIf(ifname).get_max_mtu()
            if max_mtu < int(ethernet['mtu']):
                ethernet['mtu'] = str(max_mtu)
        except:
            pass

    if 'is_bond_member' in ethernet:
        update_bond_options(conf, ethernet)

    tmp = is_node_changed(conf, base + [ifname, 'speed'])
    if tmp: ethernet.update({'speed_duplex_changed': {}})

    tmp = is_node_changed(conf, base + [ifname, 'duplex'])
    if tmp: ethernet.update({'speed_duplex_changed': {}})

    tmp = is_node_changed(conf, base + [ifname, 'evpn'])
    if tmp: ethernet.update({'frr_dict' : get_frrender_dict(conf)})

    ethernet['flowtable_interfaces'] = get_flowtable_interfaces(conf)

    ethernet['vpp'] = conf.get_config_dict(
        ['vpp'],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    # Protocols static arp dependency
    if 'static_arp' in ethernet:
        set_dependents('static_arp', conf)

    return ethernet

def verify_speed_duplex(ethernet: dict, ethtool: Ethtool):
    """
     Verify speed and duplex
    :param ethernet: dictionary which is received from get_interface_dict
    :type ethernet: dict
    :param ethtool: Ethernet object
    :type ethtool: Ethtool
    """
    if ((ethernet['speed'] == 'auto' and ethernet['duplex'] != 'auto') or
            (ethernet['speed'] != 'auto' and ethernet['duplex'] == 'auto')):
        raise ConfigError(
            'Speed/Duplex missmatch. Must be both auto or manually configured')

    if ethernet['speed'] != 'auto' and ethernet['duplex'] != 'auto':
        # We need to verify if the requested speed and duplex setting is
        # supported by the underlaying NIC.
        speed = ethernet['speed']
        duplex = ethernet['duplex']
        if not ethtool.check_speed_duplex(speed, duplex):
            raise ConfigError(
                f'Adapter does not support changing speed ' \
                f'and duplex settings to: {speed}/{duplex}!')


def verify_flow_control(ethernet: dict, ethtool: Ethtool):
    """
     Verify flow control
    :param ethernet: dictionary which is received from get_interface_dict
    :type ethernet: dict
    :param ethtool: Ethernet object
    :type ethtool: Ethtool
    """
    if 'disable_flow_control' in ethernet:
        if not ethtool.check_flow_control():
            raise ConfigError(
                'Adapter does not support changing flow-control settings!')


def verify_ring_buffer(ethernet: dict, ethtool: Ethtool):
    """
     Verify ring buffer
    :param ethernet: dictionary which is received from get_interface_dict
    :type ethernet: dict
    :param ethtool: Ethernet object
    :type ethtool: Ethtool
    """
    if 'ring_buffer' in ethernet:
        max_rx = ethtool.get_ring_buffer_max('rx')
        if not max_rx:
            raise ConfigError(
                'Driver does not support RX ring-buffer configuration!')

        max_tx = ethtool.get_ring_buffer_max('tx')
        if not max_tx:
            raise ConfigError(
                'Driver does not support TX ring-buffer configuration!')

        rx = dict_search('ring_buffer.rx', ethernet)
        if rx and int(rx) > int(max_rx):
            raise ConfigError(f'Driver only supports a maximum RX ring-buffer ' \
                              f'size of "{max_rx}" bytes!')

        tx = dict_search('ring_buffer.tx', ethernet)
        if tx and int(tx) > int(max_tx):
            raise ConfigError(f'Driver only supports a maximum TX ring-buffer ' \
                              f'size of "{max_tx}" bytes!')


def verify_coalesce(ethernet: dict, ethtool: Ethtool):
    """
    Verify coalesce settings
    :param ethernet: dictionary which is received from get_interface_dict
    :type ethernet: dict
    :param ethtool: Ethernet object
    :type ethtool: Ethtool
    """
    if 'interrupt_coalescing' in ethernet:
        if not ethtool.check_coalesce():
            raise ConfigError('Driver does not fully support coalesce configuration!')

        for param in coalesce.get_all_params():
            if param in ethernet['interrupt_coalescing']:
                if not ethtool.check_coalesce(param):
                    param_name = param.replace('_', '-')
                    msg = f'Driver does not support "{param_name}" coalesce setting!'
                    raise ConfigError(msg)


def verify_offload(ethernet: dict, ethtool: Ethtool):
    """
     Verify offloading capabilities
    :param ethernet: dictionary which is received from get_interface_dict
    :type ethernet: dict
    :param ethtool: Ethernet object
    :type ethtool: Ethtool
    """
    if dict_search('offload.rps', ethernet) != None:
        if not os.path.exists(f'/sys/class/net/{ethernet["ifname"]}/queues/rx-0/rps_cpus'):
            raise ConfigError('Interface does not suport RPS!')
    driver = ethtool.get_driver_name()
    # T3342 - Xen driver requires special treatment
    if driver == 'vif':
        if int(ethernet['mtu']) > 1500 and dict_search('offload.sg', ethernet) == None:
            raise ConfigError('Xen netback drivers requires scatter-gatter offloading '\
                              'for MTU size larger then 1500 bytes')

def verify_mac_change(ethernet: dict, ethtool: Ethtool):
    """
     Verify if ethernet card driver supports changing the interface MAC address.
     AWS ENA driver has no support for MAC address changes.

    :param ethernet: dictionary which is received from get_interface_dict
    :type ethernet: dict
    :param ethtool: Ethernet object
    :type ethtool: Ethtool
    """
    if 'mac' not in ethernet:
        return None
    if not ethtool.check_mac_change():
        raise ConfigError(f'Driver does not suport changing MAC address!')

def verify_allowedbond_changes(ethernet: dict):
    """
     Verify changed options if interface is in bonding
    :param ethernet: dictionary which is received from get_interface_dict
    :type ethernet: dict
    """
    if 'bond_blocked_changes' in ethernet:
        for option in ethernet['bond_blocked_changes']:
            raise ConfigError(f'Cannot configure "{option.replace(".", " ")}"' \
                              f' on interface "{ethernet["ifname"]}".' \
                              f' Interface is a bond member')

def verify_flowtable(ethernet: dict):
    ifname = ethernet['ifname']

    if 'deleted' in ethernet and ifname in ethernet['flowtable_interfaces']:
        raise ConfigError(f'Cannot delete interface "{ifname}", still referenced on a flowtable')

    if 'vif_remove' in ethernet:
        for vif in ethernet['vif_remove']:
            vifname = f'{ifname}.{vif}'

            if vifname in ethernet['flowtable_interfaces']:
                raise ConfigError(f'Cannot delete interface "{vifname}", still referenced on a flowtable')

    if 'vif_s_remove' in ethernet:
        for vifs in ethernet['vif_s_remove']:
            vifsname = f'{ifname}.{vifs}'

            if vifsname in ethernet['flowtable_interfaces']:
                raise ConfigError(f'Cannot delete interface "{vifsname}", still referenced on a flowtable')

    if 'vif_s' in ethernet:
        for vifs, vifs_conf in ethernet['vif_s'].items():
            if 'vif_c_delete' in vifs_conf:
                for vifc in vifs_conf['vif_c_delete']:
                    vifcname = f'{ifname}.{vifs}.{vifc}'

                    if vifcname in ethernet['flowtable_interfaces']:
                        raise ConfigError(f'Cannot delete interface "{vifcname}", still referenced on a flowtable')

def verify_vpp_remove_vif(ethernet: dict):
    """Ensure that VIF interfaces being removed are not used by VPP features"""
    vpp_paths_pattern = re.compile(
        # Known paths that already use VLAN interfaces
        r'(nat\.cgnat\.interface\.inside)|'
        r'(nat\.cgnat\.interface\.outside)|'
        r'(nat\.nat44\.interface\.inside)|'
        r'(nat\.nat44\.interface\.outside)|'
        # Potential paths for VLAN interfaces
        r'(nat\.nat44\.address_pool\.translation\.interface)|'
        r'(nat\.nat44\.address_pool\.twice_nat\.interface)|'
        r'(nat\.nat44\.exclude\.rule\.(\d)+\.external_interface)|'
        r'(interfaces\.bonding\.bond(\d)+\.member\.interface)|'
        r'(interfaces\.bridge\.br(\d)+\.member\.interface)|'
        r'(interfaces\.xconnect\.xcon(\d)+\.member\.interface)|'
        r'(acl\.ip\.interface)|'
        r'(acl\.mac\.interface)'
    )
    ifname = ethernet['ifname']

    vlan_names = [
        f'{ifname}.{vif_id}'
        for vif_group in ['vif_remove', 'vif_s_remove']
        for vif_id in ethernet.get(vif_group, [])
    ]

    if not vlan_names:
        return

    vpp_flat = dict_to_paths_values(ethernet.get('vpp', {}))

    candidate_keys = []
    for key, value in vpp_flat.items():
        # Normalize values to list for consistent processing
        values = value if isinstance(value, list) else [value]
        if any(vlan in values for vlan in vlan_names):
            candidate_keys.append((key, values))

    if not candidate_keys:
        return

    for key, values in candidate_keys:
        if vpp_paths_pattern.fullmatch(key):
            used_vlans = [v for v in vlan_names if v in values]
            if used_vlans:
                raise ConfigError(
                    f'Cannot delete interface "{used_vlans[0]}", '
                    f'it is still in use by "vpp {key.replace(".", " ")}"'
                )

def verify(ethernet):
    verify_flowtable(ethernet)
    verify_vpp_remove_vif(ethernet)

    if 'deleted' in ethernet:
        return None

    ifname = ethernet['ifname']
    verify_interface_exists(ethernet, ifname, state_required=True)
    verify_eapol(ethernet)
    verify_mirror_redirect(ethernet)
    # No need to check speed and duplex keys as both have default values
    ethtool = Ethtool(ifname)
    verify_speed_duplex(ethernet, ethtool)
    verify_flow_control(ethernet, ethtool)
    verify_ring_buffer(ethernet, ethtool)
    verify_offload(ethernet, ethtool)
    verify_mac_change(ethernet, ethtool)
    verify_coalesce(ethernet, ethtool)

    if 'is_bond_member' in ethernet:
        verify_bond_member(ethernet, ethtool)
    else:
        verify_ethernet(ethernet, ethtool)


def verify_bond_member(ethernet: dict, ethtool: Ethtool) -> None:
    """
     Verification function for ethernet interface which is in bonding
    :param ethernet: dictionary which is received from get_interface_dict
    :type ethernet: dict
    """
    verify_allowedbond_changes(ethernet)
    return None

def verify_ethernet(ethernet: dict, ethtool: Ethtool) -> None:
    """
     Verification function for simple ethernet interface
    :param ethernet: dictionary which is received from get_interface_dict
    :type ethernet: dict
    """
    verify_mtu(ethernet)
    verify_mtu_ipv6(ethernet)
    verify_dhcpv6(ethernet)
    verify_address(ethernet)
    verify_vrf(ethernet)
    verify_bond_bridge_member(ethernet)
    # use common function to verify VLAN configuration
    verify_vlan_config(ethernet)
    return None

def generate(ethernet):
    if 'frr_dict' in ethernet and not is_systemd_service_running('vyos-configd.service'):
        FRRender().generate(ethernet['frr_dict'])
    return None

def apply(ethernet):
    if 'frr_dict' in ethernet and not is_systemd_service_running('vyos-configd.service'):
        FRRender().apply()
    ifname = ethernet['ifname']
    e = EthernetIf(ifname)
    if 'deleted' in ethernet:
        e.remove()
    else:
        e.update(ethernet)
    if 'static_arp' in ethernet:
        call_dependents()

    vpp_iface_config = dict_search(f'vpp.settings.interface.{ifname}', ethernet)
    if vpp_iface_config is not None and is_systemd_service_running('vpp.service'):
        vpp_api = VPPControl()

        # Enable ip4-dhcp-client-detect feature for DHCP-configured interfaces.
        # This feature is required for VPP to process DHCP packets and assign addresses.
        if 'dhcp' in ethernet.get('address', []):
            vpp_api.enable_dhcp_client(ifname)
        else:
            vpp_api.disable_dhcp_client(ifname)

        # Enable ip6-icmp-ra-punt feature for DHCPv6-configured interfaces.
        if 'dhcpv6' in ethernet.get('address', []) or (
            'autoconf' in ethernet.get('ipv6', {}).get('address', {})
        ):
            vpp_api.enable_icmpv6_ra_punt(ifname)
        else:
            vpp_api.disable_icmpv6_ra_punt(ifname)

        # If the interface is managed by the VPP DPDK driver, synchronize runtime
        # parameters between Linux and the corresponding VPP LCP interface
        # Find LCP pair
        lcp_pair = vpp_api.lcp_pair_find(vpp_name_hw=ifname)
        # Sync MTU to VPP LCP pair interface
        if lcp_pair:
            lcp_name = lcp_pair.get('vpp_name_kernel')
            mtu = e.get_mtu()
            vpp_api.set_iface_mtu(lcp_name, mtu)

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
