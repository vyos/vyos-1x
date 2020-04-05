#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
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
from re import findall

from copy import deepcopy
from jinja2 import FileSystemLoader, Environment

from subprocess import Popen, PIPE
from netifaces import interfaces
from netaddr import EUI, mac_unix_expanded

from vyos.config import Config
from vyos.configdict import list_diff, vlan_to_dict
from vyos.defaults import directories as vyos_data_dir
from vyos.ifconfig import WiFiIf
from vyos.ifconfig_vlan import apply_vlan_config, verify_vlan_config
from vyos.util import process_running, chmod_x, chown_file
from vyos import ConfigError

user = 'root'
group = 'vyattacfg'

default_config_data = {
    'address': [],
    'address_remove': [],
    'cap_ht' : False,
    'cap_ht_40mhz_incapable' : False,
    'cap_ht_powersave' : False,
    'cap_ht_chan_set_width' : '',
    'cap_ht_delayed_block_ack' : False,
    'cap_ht_dsss_cck_40' : False,
    'cap_ht_greenfield' : False,
    'cap_ht_ldpc' : False,
    'cap_ht_lsig_protection' : False,
    'cap_ht_max_amsdu' : '',
    'cap_ht_short_gi' :  [],
    'cap_ht_smps' : '',
    'cap_ht_stbc_rx' : '',
    'cap_ht_stbc_tx' : False,
    'cap_req_ht' : False,
    'cap_req_vht' : False,
    'cap_vht' : False,
    'cap_vht_antenna_cnt' : '',
    'cap_vht_antenna_fixed' : False,
    'cap_vht_beamform' : '',
    'cap_vht_center_freq_1' : '',
    'cap_vht_center_freq_2' : '',
    'cap_vht_chan_set_width' : '',
    'cap_vht_ldpc' : False,
    'cap_vht_link_adaptation' : '',
    'cap_vht_max_mpdu_exp' : '',
    'cap_vht_max_mpdu' : '',
    'cap_vht_short_gi' : [],
    'cap_vht_stbc_rx' : '',
    'cap_vht_stbc_tx' : False,
    'cap_vht_tx_powersave' : False,
    'cap_vht_vht_cf' : False,
    'channel': '',
    'country_code': '',
    'description': '',
    'deleted': False,
    'dhcp_client_id': '',
    'dhcp_hostname': '',
    'dhcp_vendor_class_id': '',
    'dhcpv6_prm_only': False,
    'dhcpv6_temporary': False,
    'disable': False,
    'disable_broadcast_ssid' : False,
    'disable_link_detect' : 1,
    'expunge_failing_stations' : False,
    'hw_id' : '',
    'intf': '',
    'isolate_stations' : False,
    'ip_disable_arp_filter': 1,
    'ip_enable_arp_accept': 0,
    'ip_enable_arp_announce': 0,
    'ip_enable_arp_ignore': 0,
    'ipv6_autoconf': 0,
    'ipv6_eui64_prefix': '',
    'ipv6_forwarding': 1,
    'ipv6_dup_addr_detect': 1,
    'mac' : '',
    'max_stations' : '',
    'mgmt_frame_protection' : 'disabled',
    'mode' : 'g',
    'phy' : '',
    'reduce_transmit_power' : '',
    'sec_wep' : False,
    'sec_wep_key' : [],
    'sec_wpa' : False,
    'sec_wpa_cipher' : [],
    'sec_wpa_mode' : 'both',
    'sec_wpa_passphrase' : '',
    'sec_wpa_radius' : [],
    'ssid' : '',
    'op_mode' : 'monitor',
    'vif': [],
    'vif_remove': [],
    'vrf': ''
}

def get_conf_file(conf_type, intf):
    cfg_dir = '/var/run/' + conf_type

    # create directory on demand
    if not os.path.exists(cfg_dir):
        os.mkdir(cfg_dir)
        chmod_x(cfg_dir)
        chown_file(cfg_dir, user, group)

    cfg_file = cfg_dir + r'/{}.cfg'.format(intf)
    return cfg_file

def get_pid(conf_type, intf):
    cfg_dir = '/var/run/' + conf_type

    # create directory on demand
    if not os.path.exists(cfg_dir):
        os.mkdir(cfg_dir)
        chmod_x(cfg_dir)
        chown_file(cfg_dir, user, group)

    cfg_file = cfg_dir + r'/{}.pid'.format(intf)
    return cfg_file


def get_wpa_suppl_config_name(intf):
    cfg_dir = '/var/run/wpa_supplicant'

    # create directory on demand
    if not os.path.exists(cfg_dir):
        os.mkdir(cfg_dir)
        chmod_x(cfg_dir)
        chown_file(cfg_dir, user, group)

    cfg_file = cfg_dir + r'/{}.cfg'.format(intf)
    return cfg_file

def subprocess_cmd(command):
    p = Popen(command, stdout=PIPE, shell=True)
    p.communicate()

def get_config():
    wifi = deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    wifi['intf'] = os.environ['VYOS_TAGNODE_VALUE']

    # check if wireless interface has been removed
    cfg_base = 'interfaces wireless ' + wifi['intf']
    if not conf.exists(cfg_base):
        wifi['deleted'] = True
        # we can not bail out early as wireless interface can not be removed
        # Kernel will complain with: RTNETLINK answers: Operation not supported.
        # Thus we need to remove individual settings
        return wifi

    # set new configuration level
    conf.set_level(cfg_base)

    # retrieve configured interface addresses
    if conf.exists('address'):
        wifi['address'] = conf.return_values('address')

    # get interface addresses (currently effective) - to determine which
    # address is no longer valid and needs to be removed
    eff_addr = conf.return_effective_values('address')
    wifi['address_remove'] = list_diff(eff_addr, wifi['address'])

    # 40MHz intolerance, use 20MHz only
    if conf.exists('capabilities ht 40mhz-incapable'):
        wifi['cap_ht'] = True
        wifi['cap_ht_40mhz_incapable'] = True

    # WMM-PS Unscheduled Automatic Power Save Delivery [U-APSD]
    if conf.exists('capabilities ht auto-powersave'):
        wifi['cap_ht'] = True
        wifi['cap_ht_powersave'] = True

    # Supported channel set width
    if conf.exists('capabilities ht channel-set-width'):
        wifi['cap_ht'] = True
        wifi['cap_ht_chan_set_width'] = conf.return_values('capabilities ht channel-set-width')

    # HT-delayed Block Ack
    if conf.exists('capabilities ht delayed-block-ack'):
        wifi['cap_ht'] = True
        wifi['cap_ht_delayed_block_ack'] = True

    # DSSS/CCK Mode in 40 MHz
    if conf.exists('capabilities ht dsss-cck-40'):
        wifi['cap_ht'] = True
        wifi['cap_ht_dsss_cck_40'] = True

    # HT-greenfield capability
    if conf.exists('capabilities ht greenfield'):
        wifi['cap_ht'] = True
        wifi['cap_ht_greenfield'] = True

    # LDPC coding capability
    if conf.exists('capabilities ht ldpc'):
        wifi['cap_ht'] = True
        wifi['cap_ht_ldpc'] = True

    # L-SIG TXOP protection capability
    if conf.exists('capabilities ht lsig-protection'):
        wifi['cap_ht'] = True
        wifi['cap_ht_lsig_protection'] = True

    # Set Maximum A-MSDU length
    if conf.exists('capabilities ht max-amsdu'):
        wifi['cap_ht'] = True
        wifi['cap_ht_max_amsdu'] = conf.return_value('capabilities ht max-amsdu')

    # Short GI capabilities
    if conf.exists('capabilities ht short-gi'):
        wifi['cap_ht'] = True
        wifi['cap_ht_short_gi'] = conf.return_values('capabilities ht short-gi')

    # Spatial Multiplexing Power Save (SMPS) settings
    if conf.exists('capabilities ht smps'):
        wifi['cap_ht'] = True
        wifi['cap_ht_smps'] = conf.return_value('capabilities ht smps')

    # Support for receiving PPDU using STBC (Space Time Block Coding)
    if conf.exists('capabilities ht stbc rx'):
        wifi['cap_ht'] = True
        wifi['cap_ht_stbc_rx'] = conf.return_value('capabilities ht stbc rx')

    # Support for sending PPDU using STBC (Space Time Block Coding)
    if conf.exists('capabilities ht stbc tx'):
        wifi['cap_ht'] = True
        wifi['cap_ht_stbc_tx'] = True

    # Require stations to support HT PHY (reject association if they do not)
    if conf.exists('capabilities require-ht'):
        wifi['cap_req_ht'] = True

    # Require stations to support VHT PHY (reject association if they do not)
    if conf.exists('capabilities require-vht'):
        wifi['cap_req_vht'] = True

    # Number of antennas on this card
    if conf.exists('capabilities vht antenna-count'):
        wifi['cap_vht'] = True
        wifi['cap_vht_antenna_cnt'] = conf.return_value('capabilities vht antenna-count')

    # set if antenna pattern does not change during the lifetime of an association
    if conf.exists('capabilities vht antenna-pattern-fixed'):
        wifi['cap_vht'] = True
        wifi['cap_vht_antenna_fixed'] = True

    # Beamforming capabilities
    if conf.exists('capabilities vht beamform'):
        wifi['cap_vht'] = True
        wifi['cap_vht_beamform'] = conf.return_values('capabilities vht beamform')

    # VHT operating channel center frequency - center freq 1 (for use with 80, 80+80 and 160 modes)
    if conf.exists('capabilities vht center-channel-freq freq-1'):
        wifi['cap_vht'] = True
        wifi['cap_vht_center_freq_1'] = conf.return_value('capabilities vht center-channel-freq freq-1')

    # VHT operating channel center frequency - center freq 2 (for use with the 80+80 mode)
    if conf.exists('capabilities vht center-channel-freq freq-2'):
        wifi['cap_vht'] = True
        wifi['cap_vht_center_freq_2'] = conf.return_value('capabilities vht center-channel-freq freq-2')

    # VHT operating Channel width
    if conf.exists('capabilities vht channel-set-width'):
        wifi['cap_vht'] = True
        wifi['cap_vht_chan_set_width'] = conf.return_value('capabilities vht channel-set-width')

    # LDPC coding capability
    if conf.exists('capabilities vht ldpc'):
        wifi['cap_vht'] = True
        wifi['cap_vht_ldpc'] = True

    # VHT link adaptation capabilities
    if conf.exists('capabilities vht link-adaptation'):
        wifi['cap_vht'] = True
        wifi['cap_vht_link_adaptation'] = conf.return_value('capabilities vht link-adaptation')

    # Set the maximum length of A-MPDU pre-EOF padding that the station can receive
    if conf.exists('capabilities vht max-mpdu-exp'):
        wifi['cap_vht'] = True
        wifi['cap_vht_max_mpdu_exp'] = conf.return_value('capabilities vht max-mpdu-exp')

    # Increase Maximum MPDU length
    if conf.exists('capabilities vht max-mpdu'):
        wifi['cap_vht'] = True
        wifi['cap_vht_max_mpdu'] = conf.return_value('capabilities vht max-mpdu')

    # Increase Maximum MPDU length
    if conf.exists('capabilities vht short-gi'):
        wifi['cap_vht'] = True
        wifi['cap_vht_short_gi'] = conf.return_values('capabilities vht short-gi')

    # Support for receiving PPDU using STBC (Space Time Block Coding)
    if conf.exists('capabilities vht stbc rx'):
        wifi['cap_vht'] = True
        wifi['cap_vht_stbc_rx'] = conf.return_value('capabilities vht stbc rx')

    # Support for the transmission of at least 2x1 STBC (Space Time Block Coding)
    if conf.exists('capabilities vht stbc tx'):
        wifi['cap_vht'] = True
        wifi['cap_vht_stbc_tx'] = True

    # Support for VHT TXOP Power Save Mode
    if conf.exists('capabilities vht tx-powersave'):
        wifi['cap_vht'] = True
        wifi['cap_vht_tx_powersave'] = True

    # STA supports receiving a VHT variant HT Control field
    if conf.exists('capabilities vht vht-cf'):
        wifi['cap_vht'] = True
        wifi['cap_vht_vht_cf'] = True

    # Wireless radio channel
    if conf.exists('channel'):
        wifi['channel'] = conf.return_value('channel')

    # retrieve interface description
    if conf.exists('description'):
        wifi['description'] = conf.return_value('description')

    # get DHCP client identifier
    if conf.exists('dhcp-options client-id'):
        wifi['dhcp_client_id'] = conf.return_value('dhcp-options client-id')

    # DHCP client host name (overrides the system host name)
    if conf.exists('dhcp-options host-name'):
        wifi['dhcp_hostname'] = conf.return_value('dhcp-options host-name')

    # DHCP client vendor identifier
    if conf.exists('dhcp-options vendor-class-id'):
        wifi['dhcp_vendor_class_id'] = conf.return_value('dhcp-options vendor-class-id')

    # DHCPv6 only acquire config parameters, no address
    if conf.exists('dhcpv6-options parameters-only'):
        wifi['dhcpv6_prm_only'] = conf.return_value('dhcpv6-options parameters-only')

    # DHCPv6 temporary IPv6 address
    if conf.exists('dhcpv6-options temporary'):
        wifi['dhcpv6_temporary'] = conf.return_value('dhcpv6-options temporary')

    # Disable broadcast of SSID from access-point
    if conf.exists('disable-broadcast-ssid'):
        wifi['disable_broadcast_ssid'] = True

    # ignore link state changes on this interface
    if conf.exists('disable-link-detect'):
        wifi['disable_link_detect'] = 2

    # Disassociate stations based on excessive transmission failures
    if conf.exists('expunge-failing-stations'):
        wifi['expunge_failing_stations'] = True

    # retrieve real hardware address
    if conf.exists('hw-id'):
        wifi['hw_id'] = conf.return_value('hw-id')

    # Isolate stations on the AP so they cannot see each other
    if conf.exists('isolate-stations'):
        wifi['isolate_stations'] = True

    # ARP filter configuration
    if conf.exists('ip disable-arp-filter'):
        wifi['ip_disable_arp_filter'] = 0

    # ARP enable accept
    if conf.exists('ip enable-arp-accept'):
        wifi['ip_enable_arp_accept'] = 1

    # ARP enable announce
    if conf.exists('ip enable-arp-announce'):
        wifi['ip_enable_arp_announce'] = 1

    # Enable acquisition of IPv6 address using stateless autoconfig (SLAAC)
    if conf.exists('ipv6 address autoconf'):
        wifi['ipv6_autoconf'] = 1

    # Get prefix for IPv6 addressing based on MAC address (EUI-64)
    if conf.exists('ipv6 address eui64'):
        wifi['ipv6_eui64_prefix'] = conf.return_value('ipv6 address eui64')

    # ARP enable ignore
    if conf.exists('ip enable-arp-ignore'):
        wifi['ip_enable_arp_ignore'] = 1

    # Disable IPv6 forwarding on this interface
    if conf.exists('ipv6 disable-forwarding'):
        wifi['ipv6_forwarding'] = 0

    # IPv6 Duplicate Address Detection (DAD) tries
    if conf.exists('ipv6 dup-addr-detect-transmits'):
        wifi['ipv6_dup_addr_detect'] = int(conf.return_value('ipv6 dup-addr-detect-transmits'))

    # Wireless physical device
    if conf.exists('physical-device'):
        wifi['phy'] = conf.return_value('physical-device')

    # Media Access Control (MAC) address
    if conf.exists('mac'):
        wifi['mac'] = conf.return_value('mac')

    # Maximum number of wireless radio stations
    if conf.exists('max-stations'):
        wifi['max_stations'] = conf.return_value('max-stations')

    # Management Frame Protection (MFP) according to IEEE 802.11w
    if conf.exists('mgmt-frame-protection'):
        wifi['mgmt_frame_protection'] = conf.return_value('mgmt-frame-protection')

    # Wireless radio mode
    if conf.exists('mode'):
        wifi['mode'] = conf.return_value('mode')

    # retrieve VRF instance
    if conf.exists('vrf'):
        wifi['vrf'] = conf.return_value('vrf')

    # Transmission power reduction in dBm
    if conf.exists('reduce-transmit-power'):
        wifi['reduce_transmit_power'] = conf.return_value('reduce-transmit-power')

    # WEP enabled?
    if conf.exists('security wep'):
        wifi['sec_wep'] = True

    # WEP encryption key(s)
    if conf.exists('security wep key'):
        wifi['sec_wep_key'] = conf.return_values('security wep key')

    # WPA enabled?
    if conf.exists('security wpa'):
        wifi['sec_wpa'] = True

    # WPA Cipher suite
    if conf.exists('security wpa cipher'):
        wifi['sec_wpa_cipher'] = conf.return_values('security wpa cipher')

    # WPA mode
    if conf.exists('security wpa mode'):
        wifi['sec_wpa_mode'] = conf.return_value('security wpa mode')

    # WPA default ciphers depend on WPA mode
    if not wifi['sec_wpa_cipher']:
        if wifi['sec_wpa_mode'] == 'wpa':
            wifi['sec_wpa_cipher'].append('TKIP')
            wifi['sec_wpa_cipher'].append('CCMP')

        elif wifi['sec_wpa_mode'] == 'wpa2':
            wifi['sec_wpa_cipher'].append('CCMP')

        elif wifi['sec_wpa_mode'] == 'both':
            wifi['sec_wpa_cipher'].append('CCMP')
            wifi['sec_wpa_cipher'].append('TKIP')

    # WPA personal shared pass phrase
    if conf.exists('security wpa passphrase'):
        wifi['sec_wpa_passphrase'] = conf.return_value('security wpa passphrase')

    # WPA RADIUS source address
    if conf.exists('security wpa radius source-address'):
        wifi['sec_wpa_radius_source'] = conf.return_value('security wpa radius source-address')

    # WPA RADIUS server
    for server in conf.list_nodes('security wpa radius server'):
        # set new configuration level
        conf.set_level(cfg_base + ' security wpa radius server ' + server)
        radius = {
            'server' : server,
            'acc_port' : '',
            'disabled': False,
            'port' : 1812,
            'key' : ''
        }

        # RADIUS server port
        if conf.exists('port'):
            radius['port'] = int(conf.return_value('port'))

        # receive RADIUS accounting info
        if conf.exists('accounting'):
            radius['acc_port'] = radius['port'] + 1

        # Check if RADIUS server was temporary disabled
        if conf.exists(['disable']):
            radius['disabled'] = True

        # RADIUS server shared-secret
        if conf.exists('key'):
            radius['key'] = conf.return_value('key')

        # append RADIUS server to list of servers
        wifi['sec_wpa_radius'].append(radius)

    # re-set configuration level to parse new nodes
    conf.set_level(cfg_base)

    # Wireless access-point service set identifier (SSID)
    if conf.exists('ssid'):
        wifi['ssid'] = conf.return_value('ssid')

    # Wireless device type for this interface
    if conf.exists('type'):
        tmp = conf.return_value('type')
        if tmp == 'access-point':
            tmp = 'ap'

        wifi['op_mode'] = tmp

    # re-set configuration level to parse new nodes
    conf.set_level(cfg_base)
    # Determine vif interfaces (currently effective) - to determine which
    # vif interface is no longer present and needs to be removed
    eff_intf = conf.list_effective_nodes('vif')
    act_intf = conf.list_nodes('vif')
    wifi['vif_remove'] = list_diff(eff_intf, act_intf)

    if conf.exists('vif'):
        for vif in conf.list_nodes('vif'):
            # set config level to vif interface
            conf.set_level(cfg_base + ' vif ' + vif)
            wifi['vif'].append(vlan_to_dict(conf))

    # disable interface
    if conf.exists('disable'):
        wifi['disable'] = True

    # retrieve configured regulatory domain
    conf.set_level('system')
    if conf.exists('wifi-regulatory-domain'):
        wifi['country_code'] = conf.return_value('wifi-regulatory-domain')

    return wifi


def verify(wifi):
    if wifi['deleted']:
        return None

    if wifi['op_mode'] != 'monitor' and not wifi['ssid']:
        raise ConfigError('SSID must be set for {}'.format(wifi['intf']))

    if not wifi['phy']:
        raise ConfigError('You must specify physical-device')

    if wifi['op_mode'] == 'ap':
        c = Config()
        if not c.exists('system wifi-regulatory-domain'):
            raise ConfigError('Wireless regulatory domain is mandatory,\n' \
                              'use "set system wifi-regulatory-domain".')

        if not wifi['channel']:
            raise ConfigError('Channel must be set for {}'.format(wifi['intf']))

    if len(wifi['sec_wep_key']) > 4:
        raise ConfigError('No more then 4 WEP keys configurable')

    if wifi['cap_vht'] and not wifi['cap_ht']:
        raise ConfigError('Specify HT flags if you want to use VHT!')

    if wifi['cap_vht_beamform'] and wifi['cap_vht_antenna_cnt'] == 1:
        raise ConfigError('Cannot use beam forming with just one antenna!')

    if wifi['cap_vht_beamform'] == 'single-user-beamformer' and wifi['cap_vht_antenna_cnt'] < 3:
        # Nasty Gotcha: see https://w1.fi/cgit/hostap/plain/hostapd/hostapd.conf lines 692-705
        raise ConfigError('Single-user beam former requires at least 3 antennas!')

    if wifi['sec_wep'] and (len(wifi['sec_wep_key']) == 0):
        raise ConfigError('Missing WEP keys')

    if wifi['sec_wpa'] and not (wifi['sec_wpa_passphrase'] or wifi['sec_wpa_radius']):
        raise ConfigError('Misssing WPA key or RADIUS server')

    for radius in wifi['sec_wpa_radius']:
        if not radius['key']:
            raise ConfigError('Misssing RADIUS shared secret key for server: {}'.format(radius['server']))

    vrf_name = wifi['vrf']
    if vrf_name and vrf_name not in interfaces():
        raise ConfigError(f'VRF "{vrf_name}" does not exist')

    # use common function to verify VLAN configuration
    verify_vlan_config(wifi)

    conf = Config()
    # Only one wireless interface per phy can be in station mode
    base = ['interfaces', 'wireless']
    for phy in os.listdir('/sys/class/ieee80211'):
        stations = []
        for wlan in conf.list_nodes(base):
            # the following node is mandatory
            if conf.exists(base + [wlan, 'physical-device', phy]):
                tmp = conf.return_value(base + [wlan, 'type'])
                if tmp == 'station':
                    stations.append(wlan)

        if len(stations) > 1:
            raise ConfigError('Only one station per wireless physical interface possible!')

    return None

def generate(wifi):
    # Prepare Jinja2 template loader from files
    tmpl_path = os.path.join(vyos_data_dir["data"], "templates", "wifi")
    fs_loader = FileSystemLoader(tmpl_path)
    env = Environment(loader=fs_loader)

    # always stop hostapd service first before reconfiguring it
    pidfile = get_pid('hostapd', wifi['intf'])
    if process_running(pidfile):
        cmd = 'start-stop-daemon'
        cmd += ' --stop '
        cmd += ' --quiet'
        cmd += ' --oknodo'
        cmd += ' --pidfile ' + pidfile
        subprocess_cmd(cmd)

    # always stop wpa_supplicant service first before reconfiguring it
    pidfile = get_pid('wpa_supplicant', wifi['intf'])
    if process_running(pidfile):
        cmd = 'start-stop-daemon'
        cmd += ' --stop '
        cmd += ' --quiet'
        cmd += ' --oknodo'
        cmd += ' --pidfile ' + pidfile
        subprocess_cmd(cmd)

    # Delete config files if interface is removed
    if wifi['deleted']:
        if os.path.isfile(get_conf_file('hostapd', wifi['intf'])):
            os.unlink(get_conf_file('hostapd', wifi['intf']))

        if os.path.isfile(get_conf_file('wpa_supplicant', wifi['intf'])):
            os.unlink(get_conf_file('wpa_supplicant', wifi['intf']))

        return None

    if not wifi['mac']:
        # http://wiki.stocksy.co.uk/wiki/Multiple_SSIDs_with_hostapd
        # generate locally administered MAC address from used phy interface
        with open('/sys/class/ieee80211/{}/addresses'.format(wifi['phy']), 'r') as f:
            # some PHYs tend to have multiple interfaces and thus supply multiple MAC
            # addresses - we only need the first one for our calculation
            tmp = f.readline().rstrip()
            tmp = EUI(tmp).value
            # mask last nibble from the MAC address
            tmp &= 0xfffffffffff0
            # set locally administered bit in MAC address
            tmp |= 0x020000000000
            # we now need to add an offset to our MAC address indicating this
            # subinterfaces index
            tmp += int(findall(r'\d+', wifi['intf'])[0])

            # convert integer to "real" MAC address representation
            mac = EUI(hex(tmp).split('x')[-1])
            # change dialect to use : as delimiter instead of -
            mac.dialect = mac_unix_expanded
            wifi['mac'] = str(mac)

    # render appropriate new config files depending on access-point or station mode
    if wifi['op_mode'] == 'ap':
        tmpl = env.get_template('hostapd.conf.tmpl')
        config_text = tmpl.render(wifi)
        with open(get_conf_file('hostapd', wifi['intf']), 'w') as f:
            f.write(config_text)

    elif wifi['op_mode'] == 'station':
        tmpl = env.get_template('wpa_supplicant.conf.tmpl')
        config_text = tmpl.render(wifi)
        with open(get_conf_file('wpa_supplicant', wifi['intf']), 'w') as f:
            f.write(config_text)

    return None

def apply(wifi):
    if wifi['deleted']:
        w = WiFiIf(wifi['intf'])
        # delete interface
        w.remove()
    else:
        # WiFi interface needs to be created on-block (e.g. mode or physical
        # interface) instead of passing a ton of arguments, I just use a dict
        # that is managed by vyos.ifconfig
        conf = deepcopy(WiFiIf.get_config())

        # Assign WiFi instance configuration parameters to config dict
        conf['phy'] = wifi['phy']

        # Finally create the new interface
        w = WiFiIf(wifi['intf'], **conf)

        # assign/remove VRF
        w.set_vrf(wifi['vrf'])

        # update interface description used e.g. within SNMP
        w.set_alias(wifi['description'])

        # get DHCP config dictionary and update values
        opt = w.get_dhcp_options()

        if wifi['dhcp_client_id']:
            opt['client_id'] = wifi['dhcp_client_id']

        if wifi['dhcp_hostname']:
            opt['hostname'] = wifi['dhcp_hostname']

        if wifi['dhcp_vendor_class_id']:
            opt['vendor_class_id'] = wifi['dhcp_vendor_class_id']

        # store DHCP config dictionary - used later on when addresses are aquired
        w.set_dhcp_options(opt)

        # get DHCPv6 config dictionary and update values
        opt = w.get_dhcpv6_options()

        if wifi['dhcpv6_prm_only']:
            opt['dhcpv6_prm_only'] = True

        if wifi['dhcpv6_temporary']:
            opt['dhcpv6_temporary'] = True

        # store DHCPv6 config dictionary - used later on when addresses are aquired
        w.set_dhcpv6_options(opt)

        # ignore link state changes
        w.set_link_detect(wifi['disable_link_detect'])

        # Change interface MAC address - re-set to real hardware address (hw-id)
        # if custom mac is removed
        if wifi['mac']:
            w.set_mac(wifi['mac'])
        elif wifi['hw_id']:
            w.set_mac(wifi['hw_id'])

        # configure ARP filter configuration
        w.set_arp_filter(wifi['ip_disable_arp_filter'])
        # configure ARP accept
        w.set_arp_accept(wifi['ip_enable_arp_accept'])
        # configure ARP announce
        w.set_arp_announce(wifi['ip_enable_arp_announce'])
        # configure ARP ignore
        w.set_arp_ignore(wifi['ip_enable_arp_ignore'])
        # IPv6 address autoconfiguration
        w.set_ipv6_autoconf(wifi['ipv6_autoconf'])
        # IPv6 EUI-based address
        w.set_ipv6_eui64_address(wifi['ipv6_eui64_prefix'])
        # IPv6 forwarding
        w.set_ipv6_forwarding(wifi['ipv6_forwarding'])
        # IPv6 Duplicate Address Detection (DAD) tries
        w.set_ipv6_dad_messages(wifi['ipv6_dup_addr_detect'])

        # Configure interface address(es)
        # - not longer required addresses get removed first
        # - newly addresses will be added second
        for addr in wifi['address_remove']:
            w.del_addr(addr)
        for addr in wifi['address']:
            w.add_addr(addr)

        # remove no longer required VLAN interfaces (vif)
        for vif in wifi['vif_remove']:
            e.del_vlan(vif)

        # create VLAN interfaces (vif)
        for vif in wifi['vif']:
            # QoS priority mapping can only be set during interface creation
            # so we delete the interface first if required.
            if vif['egress_qos_changed'] or vif['ingress_qos_changed']:
                try:
                    # on system bootup the above condition is true but the interface
                    # does not exists, which throws an exception, but that's legal
                    e.del_vlan(vif['id'])
                except:
                    pass

            vlan = e.add_vlan(vif['id'])
            apply_vlan_config(vlan, vif)

        # Enable/Disable interface - interface is always placed in
        # administrative down state in WiFiIf class
        if not wifi['disable']:
            w.set_admin_state('up')

            # Physical interface is now configured. Proceed by starting hostapd or
            # wpa_supplicant daemon. When type is monitor we can just skip this.
            if wifi['op_mode'] == 'ap':
                cmd  = 'start-stop-daemon'
                cmd += ' --start '
                cmd += ' --quiet'
                cmd += ' --oknodo'
                cmd += ' --pidfile ' + get_pid('hostapd', wifi['intf'])
                cmd += ' --exec /usr/sbin/hostapd'
                # now pass arguments to hostapd binary
                cmd += ' -- '
                cmd += ' -B'
                cmd += ' -P ' + get_pid('hostapd', wifi['intf'])
                cmd += ' ' + get_conf_file('hostapd', wifi['intf'])

                # execute assembled command
                subprocess_cmd(cmd)

            elif wifi['op_mode'] == 'station':
                cmd  = 'start-stop-daemon'
                cmd += ' --start '
                cmd += ' --quiet'
                cmd += ' --oknodo'
                cmd += ' --pidfile ' + get_pid('hostapd', wifi['intf'])
                cmd += ' --exec /sbin/wpa_supplicant'
                # now pass arguments to hostapd binary
                cmd += ' -- '
                cmd += ' -s -B -D nl80211'
                cmd += ' -P ' + get_pid('wpa_supplicant', wifi['intf'])
                cmd += ' -i ' + wifi['intf']
                cmd += ' -c ' + get_conf_file('wpa_supplicant', wifi['intf'])

                # execute assembled command
                subprocess_cmd(cmd)

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
