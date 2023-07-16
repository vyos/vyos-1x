#!/usr/bin/env python3
#
# Copyright (C) 2019-2023 VyOS maintainers and contributors
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
from vyos.configdict import get_interface_dict
from vyos.configdict import is_node_changed
from vyos.configverify import verify_address
from vyos.configverify import verify_dhcpv6
from vyos.configverify import verify_eapol
from vyos.configverify import verify_interface_exists
from vyos.configverify import verify_mirror_redirect
from vyos.configverify import verify_mtu
from vyos.configverify import verify_mtu_ipv6
from vyos.configverify import verify_vlan_config
from vyos.configverify import verify_vrf
from vyos.configverify import verify_bond_bridge_member
from vyos.validate import is_bond_member_allowed_option
from vyos.ethtool import Ethtool
from vyos.ifconfig import EthernetIf
from vyos.pki import find_chain
from vyos.pki import encode_certificate
from vyos.pki import load_certificate
from vyos.pki import wrap_private_key
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.dict import dict_search
from vyos.utils.file import write_file
from vyos import ConfigError
from vyos import airbag


airbag.enable()

# XXX: wpa_supplicant works on the source interface
cfg_dir = '/run/wpa_supplicant'
wpa_suppl_conf = '/run/wpa_supplicant/{ifname}.conf'


def remove_blocked_options(conf: Config, ethernet: dict):
    """
    Remove unused options if interface is in bonding.
    If unused option was changed, it is added to ethernet['bond_blocked_changes']
    as a list for verifying
    :param conf: Configuration
    :type conf: Config
    :param ethernet: dictionary which is received from get_interface_dict
    :type ethernet:dict
    """
    config_with_defaults = conf.get_config_dict(
        ['interfaces', 'ethernet', ethernet['ifname']],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_defaults=True,
        with_recursive_defaults=True)
    config_without_defaults = conf.get_config_dict(
        ['interfaces', 'ethernet', ethernet['ifname']],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_defaults=False,
        with_recursive_defaults=False)

    list_blocked_changes = []
    list_keys = list(ethernet.keys())
    for option in list_keys:
        if not is_bond_member_allowed_option(option):
            if option in config_with_defaults:
                del ethernet[option]
            if option in config_without_defaults:
                list_blocked_changes.append(option)
    ethernet['bond_blocked_changes'] = list_blocked_changes


def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()

    # This must be called prior to get_interface_dict(), as this function will
    # alter the config level (config.set_level())
    pki = conf.get_config_dict(['pki'], key_mangling=('-', '_'),
                               get_first_key=True,
                               no_tag_node_value_mangle=True)

    base = ['interfaces', 'ethernet']
    ifname, ethernet = get_interface_dict(conf, base)

    if 'is_bond_member' in ethernet:
        remove_blocked_options(conf, ethernet)
    if 'deleted' not in ethernet:
        if pki: ethernet['pki'] = pki

    tmp = is_node_changed(conf, base + [ifname, 'speed'])
    if tmp: ethernet.update({'speed_duplex_changed': {}})

    tmp = is_node_changed(conf, base + [ifname, 'duplex'])
    if tmp: ethernet.update({'speed_duplex_changed': {}})

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


def verify_allowedbond_changes(ethernet: dict):
    """
     Verify changed options if interface is in bonding
    :param ethernet: dictionary which is received from get_interface_dict
    :type ethernet: dict
    """
    if ethernet['bond_blocked_changes']:
        for option in ethernet['bond_blocked_changes']:
            raise ConfigError(f'Cannot configure {option} ' \
                              f'on interface {ethernet["ifname"]}.' \
                              f' Interface is a bond member')


def verify(ethernet):
    if 'deleted' in ethernet:
        return None
    if 'is_bond_member' in ethernet:
        verify_bond_member(ethernet)
    else:
        verify_ethernet(ethernet)


def verify_bond_member(ethernet):
    """
     Verification function for ethernet interface which is in bonding
    :param ethernet: dictionary which is received from get_interface_dict
    :type ethernet: dict
    """
    ifname = ethernet['ifname']
    verify_interface_exists(ifname)
    verify_bond_bridge_member(ethernet)
    verify_eapol(ethernet)
    verify_mirror_redirect(ethernet)
    ethtool = Ethtool(ifname)
    verify_speed_duplex(ethernet, ethtool)
    verify_flow_control(ethernet, ethtool)
    verify_ring_buffer(ethernet, ethtool)
    verify_offload(ethernet, ethtool)
    verify_allowedbond_changes(ethernet)

def verify_ethernet(ethernet):
    """
     Verification function for simple ethernet interface
    :param ethernet: dictionary which is received from get_interface_dict
    :type ethernet: dict
    """
    ifname = ethernet['ifname']
    verify_interface_exists(ifname)
    verify_mtu(ethernet)
    verify_mtu_ipv6(ethernet)
    verify_dhcpv6(ethernet)
    verify_address(ethernet)
    verify_vrf(ethernet)
    verify_bond_bridge_member(ethernet)
    verify_eapol(ethernet)
    verify_mirror_redirect(ethernet)
    ethtool = Ethtool(ifname)
    # No need to check speed and duplex keys as both have default values.
    verify_speed_duplex(ethernet, ethtool)
    verify_flow_control(ethernet, ethtool)
    verify_ring_buffer(ethernet, ethtool)
    verify_offload(ethernet, ethtool)
    # use common function to verify VLAN configuration
    verify_vlan_config(ethernet)
    return None


def generate(ethernet):
    # render real configuration file once
    wpa_supplicant_conf = wpa_suppl_conf.format(**ethernet)

    if 'deleted' in ethernet:
        # delete configuration on interface removal
        if os.path.isfile(wpa_supplicant_conf):
            os.unlink(wpa_supplicant_conf)
        return None

    if 'eapol' in ethernet:
        ifname = ethernet['ifname']

        render(wpa_supplicant_conf, 'ethernet/wpa_supplicant.conf.j2', ethernet)

        cert_file_path = os.path.join(cfg_dir, f'{ifname}_cert.pem')
        cert_key_path = os.path.join(cfg_dir, f'{ifname}_cert.key')

        cert_name = ethernet['eapol']['certificate']
        pki_cert = ethernet['pki']['certificate'][cert_name]

        loaded_pki_cert = load_certificate(pki_cert['certificate'])
        loaded_ca_certs = {load_certificate(c['certificate'])
            for c in ethernet['pki']['ca'].values()} if 'ca' in ethernet['pki'] else {}

        cert_full_chain = find_chain(loaded_pki_cert, loaded_ca_certs)

        write_file(cert_file_path,
                   '\n'.join(encode_certificate(c) for c in cert_full_chain))
        write_file(cert_key_path, wrap_private_key(pki_cert['private']['key']))

        if 'ca_certificate' in ethernet['eapol']:
            ca_cert_file_path = os.path.join(cfg_dir, f'{ifname}_ca.pem')
            ca_cert_name = ethernet['eapol']['ca_certificate']
            pki_ca_cert = ethernet['pki']['ca'][ca_cert_name]

            loaded_ca_cert = load_certificate(pki_ca_cert['certificate'])
            ca_full_chain = find_chain(loaded_ca_cert, loaded_ca_certs)

            write_file(ca_cert_file_path,
                       '\n'.join(encode_certificate(c) for c in ca_full_chain))

    return None

def apply(ethernet):
    ifname = ethernet['ifname']
    # take care about EAPoL supplicant daemon
    eapol_action='stop'

    e = EthernetIf(ifname)
    if 'deleted' in ethernet:
        # delete interface
        e.remove()
    else:
        e.update(ethernet)
        if 'eapol' in ethernet:
            eapol_action='reload-or-restart'

    call(f'systemctl {eapol_action} wpa_supplicant-wired@{ifname}')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
