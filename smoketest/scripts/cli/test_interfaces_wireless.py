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

import os
import re
import unittest

from base_interfaces_test import BasicInterfaceTest
from glob import glob

from vyos.configsession import ConfigSessionError
from vyos.utils.file import read_file
from vyos.utils.kernel import check_kmod
from vyos.utils.network import interface_exists
from vyos.utils.process import process_named_running
from vyos.utils.process import call
from vyos.xml_ref import default_value

def get_config_value(interface, key):
    tmp = read_file(f'/run/hostapd/{interface}.conf')
    tmp = re.findall(f'{key}=+(.*)', tmp)
    return tmp[0]

wifi_cc_path = ['system', 'wireless', 'country-code']
country = 'se'
class WirelessInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['interfaces', 'wireless']
        cls._options = {
            'wlan0':  ['physical-device phy0',
                       'ssid VyOS-WIFI-0',
                       'type station',
                       'address 192.0.2.1/30'],
            'wlan1':  ['physical-device phy0',
                       'ssid VyOS-WIFI-1',
                       'type access-point',
                       'address 192.0.2.5/30',
                       'channel 0'],
            'wlan10': ['physical-device phy1',
                       'ssid VyOS-WIFI-2',
                       'type station',
                       'address 192.0.2.9/30'],
            'wlan11': ['physical-device phy1',
                       'ssid VyOS-WIFI-3',
                       'type access-point',
                       'address 192.0.2.13/30',
                       'channel 0'],
        }
        cls._interfaces = list(cls._options)
        # call base-classes classmethod
        super(WirelessInterfaceTest, cls).setUpClass()

        # T5245 - currently testcases are disabled
        cls._test_ipv6 = False
        cls._test_vlan = False

        cls.cli_set(cls, wifi_cc_path + [country])


    def test_wireless_add_single_ip_address(self):
        # derived method to check if member interfaces are enslaved properly
        super().test_add_single_ip_address()

        for option, option_value in self._options.items():
            if 'type access-point' in option_value:
                # Check for running process
                self.assertTrue(process_named_running('hostapd'))
            elif 'type station' in option_value:
                # Check for running process
                self.assertTrue(process_named_running('wpa_supplicant'))
            else:
                self.assertTrue(False)

    def test_wireless_hostapd_config(self):
        # Only set the hostapd (access-point) options
        interface = self._interfaces[1] # wlan1
        ssid = 'ssid'

        self.cli_set(self._base_path + [interface, 'ssid', ssid])
        self.cli_set(self._base_path + [interface, 'type', 'access-point'])

        # auto-powersave is special
        self.cli_set(self._base_path + [interface, 'capabilities', 'ht', 'auto-powersave'])

        ht_opt = {
            # VyOS CLI option           hostapd - ht_capab setting
            '40mhz-incapable'         : '[40-INTOLERANT]',
            'delayed-block-ack'       : '[DELAYED-BA]',
            'greenfield'              : '[GF]',
            'ldpc'                    : '[LDPC]',
            'lsig-protection'         : '[LSIG-TXOP-PROT]',
            'channel-set-width ht40+' : '[HT40+]',
            'stbc tx'                 : '[TX-STBC]',
            'stbc rx 123'             : '[RX-STBC-123]',
            'max-amsdu 7935'          : '[MAX-AMSDU-7935]',
            'smps static'             : '[SMPS-STATIC]',
        }
        for key in ht_opt:
            self.cli_set(self._base_path + [interface, 'capabilities', 'ht'] + key.split())

        vht_opt = {
            # VyOS CLI option           hostapd - ht_capab setting
            'channel-set-width 3'     : '[VHT160-80PLUS80]',
            'stbc tx'                 : '[TX-STBC-2BY1]',
            'stbc rx 12'              : '[RX-STBC-12]',
            'ldpc'                    : '[RXLDPC]',
            'tx-powersave'            : '[VHT-TXOP-PS]',
            'vht-cf'                  : '[HTC-VHT]',
            'antenna-pattern-fixed'   : '[RX-ANTENNA-PATTERN][TX-ANTENNA-PATTERN]',
            'max-mpdu 11454'          : '[MAX-MPDU-11454]',
            'max-mpdu-exp 2'          : '[MAX-A-MPDU-LEN-EXP-2]',
            'link-adaptation both'    : '[VHT-LINK-ADAPT3]',
            'short-gi 80'             : '[SHORT-GI-80]',
            'short-gi 160'            : '[SHORT-GI-160]',
        }
        for key in vht_opt:
            self.cli_set(self._base_path + [interface, 'capabilities', 'vht'] + key.split())

        self.cli_commit()

        #
        # Validate Config
        #
        tmp = get_config_value(interface, 'interface')
        self.assertEqual(interface, tmp)

        # ssid
        tmp = get_config_value(interface, 'ssid')
        self.assertEqual(ssid, tmp)

        # channel
        tmp = get_config_value(interface, 'channel')
        cli_default = default_value(self._base_path + [interface, 'channel'])
        self.assertEqual(cli_default, tmp)

        # auto-powersave is special
        tmp = get_config_value(interface, 'uapsd_advertisement_enabled')
        self.assertEqual('1', tmp)

        tmp = get_config_value(interface, 'ht_capab')
        for key, value in ht_opt.items():
            self.assertIn(value, tmp)

        tmp = get_config_value(interface, 'vht_capab')
        for key, value in vht_opt.items():
            self.assertIn(value, tmp)

        # Check for running process
        self.assertTrue(process_named_running('hostapd'))

    def test_wireless_hostapd_vht_mu_beamformer_config(self):
        # Multi-User-Beamformer
        interface = self._interfaces[1] # wlan1
        ssid = 'vht_mu-beamformer'
        antennas = '3'

        self.cli_set(self._base_path + [interface, 'ssid', ssid])
        self.cli_set(self._base_path + [interface, 'type', 'access-point'])
        self.cli_set(self._base_path + [interface, 'channel', '36'])

        ht_opt = {
            # VyOS CLI option           hostapd - ht_capab setting
            'channel-set-width ht20'  : '[HT20]',
            'channel-set-width ht40-' : '[HT40-]',
            'channel-set-width ht40+' : '[HT40+]',
            'dsss-cck-40'             : '[DSSS_CCK-40]',
            'short-gi 20'             : '[SHORT-GI-20]',
            'short-gi 40'             : '[SHORT-GI-40]',
            'max-amsdu 7935'          : '[MAX-AMSDU-7935]',
        }
        for key in ht_opt:
            self.cli_set(self._base_path + [interface, 'capabilities', 'ht'] + key.split())

        vht_opt = {
            # VyOS CLI option           hostapd - ht_capab setting
            'max-mpdu 11454'          : '[MAX-MPDU-11454]',
            'max-mpdu-exp 2'          : '[MAX-A-MPDU-LEN-EXP-2]',
            'stbc tx'                 : '[TX-STBC-2BY1]',
            'stbc rx 12'              : '[RX-STBC-12]',
            'ldpc'                    : '[RXLDPC]',
            'tx-powersave'            : '[VHT-TXOP-PS]',
            'vht-cf'                  : '[HTC-VHT]',
            'antenna-pattern-fixed'   : '[RX-ANTENNA-PATTERN][TX-ANTENNA-PATTERN]',
            'link-adaptation both'    : '[VHT-LINK-ADAPT3]',
            'short-gi 80'             : '[SHORT-GI-80]',
            'short-gi 160'            : '[SHORT-GI-160]',
            'beamform multi-user-beamformer' : '[MU-BEAMFORMER][BF-ANTENNA-3][SOUNDING-DIMENSION-3]',
        }

        self.cli_set(self._base_path + [interface, 'capabilities', 'vht', 'channel-set-width', '1'])
        self.cli_set(self._base_path + [interface, 'capabilities', 'vht', 'center-channel-freq', 'freq-1', '42'])
        self.cli_set(self._base_path + [interface, 'capabilities', 'vht', 'antenna-count', antennas])
        for key in vht_opt:
            self.cli_set(self._base_path + [interface, 'capabilities', 'vht'] + key.split())

        self.cli_commit()

        #
        # Validate Config
        #
        tmp = get_config_value(interface, 'interface')
        self.assertEqual(interface, tmp)

        # ssid
        tmp = get_config_value(interface, 'ssid')
        self.assertEqual(ssid, tmp)

        # channel
        tmp = get_config_value(interface, 'channel')
        self.assertEqual('36', tmp)

        tmp = get_config_value(interface, 'ht_capab')
        for key, value in ht_opt.items():
            self.assertIn(value, tmp)

        tmp = get_config_value(interface, 'vht_capab')
        for key, value in vht_opt.items():
            self.assertIn(value, tmp)

    def test_wireless_hostapd_vht_su_beamformer_config(self):
        # Single-User-Beamformer
        interface = self._interfaces[1] # wlan1
        ssid = 'vht_su-beamformer'
        antennas = '3'

        self.cli_set(self._base_path + [interface, 'ssid', ssid])
        self.cli_set(self._base_path + [interface, 'type', 'access-point'])
        self.cli_set(self._base_path + [interface, 'channel', '36'])

        ht_opt = {
            # VyOS CLI option           hostapd - ht_capab setting
            'channel-set-width ht20'  : '[HT20]',
            'channel-set-width ht40-' : '[HT40-]',
            'channel-set-width ht40+' : '[HT40+]',
            'dsss-cck-40'             : '[DSSS_CCK-40]',
            'short-gi 20'             : '[SHORT-GI-20]',
            'short-gi 40'             : '[SHORT-GI-40]',
            'max-amsdu 7935'          : '[MAX-AMSDU-7935]',
        }
        for key in ht_opt:
            self.cli_set(self._base_path + [interface, 'capabilities', 'ht'] + key.split())

        vht_opt = {
            # VyOS CLI option           hostapd - ht_capab setting
            'max-mpdu 11454'          : '[MAX-MPDU-11454]',
            'max-mpdu-exp 2'          : '[MAX-A-MPDU-LEN-EXP-2]',
            'stbc tx'                 : '[TX-STBC-2BY1]',
            'stbc rx 12'              : '[RX-STBC-12]',
            'ldpc'                    : '[RXLDPC]',
            'tx-powersave'            : '[VHT-TXOP-PS]',
            'vht-cf'                  : '[HTC-VHT]',
            'antenna-pattern-fixed'   : '[RX-ANTENNA-PATTERN][TX-ANTENNA-PATTERN]',
            'link-adaptation both'    : '[VHT-LINK-ADAPT3]',
            'short-gi 80'             : '[SHORT-GI-80]',
            'short-gi 160'            : '[SHORT-GI-160]',
            'beamform single-user-beamformer' : '[SU-BEAMFORMER][BF-ANTENNA-2][SOUNDING-DIMENSION-2]',
        }

        self.cli_set(self._base_path + [interface, 'capabilities', 'vht', 'channel-set-width', '1'])
        self.cli_set(self._base_path + [interface, 'capabilities', 'vht', 'center-channel-freq', 'freq-1', '42'])
        self.cli_set(self._base_path + [interface, 'capabilities', 'vht', 'antenna-count', antennas])
        for key in vht_opt:
            self.cli_set(self._base_path + [interface, 'capabilities', 'vht'] + key.split())

        self.cli_commit()

        #
        # Validate Config
        #
        tmp = get_config_value(interface, 'interface')
        self.assertEqual(interface, tmp)

        # ssid
        tmp = get_config_value(interface, 'ssid')
        self.assertEqual(ssid, tmp)

        # channel
        tmp = get_config_value(interface, 'channel')
        self.assertEqual('36', tmp)

        tmp = get_config_value(interface, 'ht_capab')
        for key, value in ht_opt.items():
            self.assertIn(value, tmp)

        tmp = get_config_value(interface, 'vht_capab')
        for key, value in vht_opt.items():
            self.assertIn(value, tmp)

    def test_wireless_hostapd_he_2ghz_config(self):
        # Only set the hostapd (access-point) options - HE mode for 802.11ax at 2.4GHz
        interface = self._interfaces[1] # wlan1
        ssid = 'ssid'
        channel = '1'
        sae_pw = 'VyOSVyOSVyOS'
        bss_color = '13'
        channel_set_width = '81'

        self.cli_set(self._base_path + [interface, 'ssid', ssid])
        self.cli_set(self._base_path + [interface, 'type', 'access-point'])
        self.cli_set(self._base_path + [interface, 'channel', channel])
        self.cli_set(self._base_path + [interface, 'mode', 'ax'])
        self.cli_set(self._base_path + [interface, 'security', 'wpa', 'mode', 'wpa2'])
        self.cli_set(self._base_path + [interface, 'security', 'wpa', 'passphrase', sae_pw])
        self.cli_set(self._base_path + [interface, 'security', 'wpa', 'cipher', 'CCMP'])
        self.cli_set(self._base_path + [interface, 'security', 'wpa', 'cipher', 'GCMP'])
        self.cli_set(self._base_path + [interface, 'capabilities', 'ht', '40mhz-incapable'])
        self.cli_set(self._base_path + [interface, 'capabilities', 'ht', 'channel-set-width', 'ht20'])
        self.cli_set(self._base_path + [interface, 'capabilities', 'ht', 'channel-set-width', 'ht40+'])
        self.cli_set(self._base_path + [interface, 'capabilities', 'ht', 'channel-set-width', 'ht40-'])
        self.cli_set(self._base_path + [interface, 'capabilities', 'ht', 'short-gi', '20'])
        self.cli_set(self._base_path + [interface, 'capabilities', 'ht', 'short-gi', '40'])
        self.cli_set(self._base_path + [interface, 'capabilities', 'he', 'bss-color', bss_color])
        self.cli_set(self._base_path + [interface, 'capabilities', 'he', 'channel-set-width', channel_set_width])
        self.cli_set(self._base_path + [interface, 'capabilities', 'he', 'beamform', 'multi-user-beamformer'])
        self.cli_set(self._base_path + [interface, 'capabilities', 'he', 'beamform', 'single-user-beamformer'])
        self.cli_set(self._base_path + [interface, 'capabilities', 'he', 'beamform', 'single-user-beamformee'])

        self.cli_commit()

        #
        # Validate Config
        #
        tmp = get_config_value(interface, 'interface')
        self.assertEqual(interface, tmp)

        # ssid
        tmp = get_config_value(interface, 'ssid')
        self.assertEqual(ssid, tmp)

        # mode of operation resulting from [interface, 'mode', 'ax']
        tmp = get_config_value(interface, 'hw_mode')
        self.assertEqual('g', tmp)
        tmp = get_config_value(interface, 'ieee80211h')
        self.assertEqual('1', tmp)
        tmp = get_config_value(interface, 'ieee80211ax')
        self.assertEqual('1', tmp)

        # channel and channel width
        tmp = get_config_value(interface, 'channel')
        self.assertEqual(channel, tmp)
        tmp = get_config_value(interface, 'op_class')
        self.assertEqual(channel_set_width, tmp)

        # BSS coloring
        tmp = get_config_value(interface, 'he_bss_color')
        self.assertEqual(bss_color, tmp)

        # sae_password
        tmp = get_config_value(interface, 'wpa_passphrase')
        self.assertEqual(sae_pw, tmp)

        # WPA3 and dependencies
        tmp = get_config_value(interface, 'wpa')
        self.assertEqual('2', tmp)
        tmp = get_config_value(interface, 'rsn_pairwise')
        self.assertEqual('CCMP GCMP', tmp)
        tmp = get_config_value(interface, 'wpa_key_mgmt')
        self.assertEqual('WPA-PSK WPA-PSK-SHA256', tmp)

        # beamforming
        tmp = get_config_value(interface, 'he_mu_beamformer')
        self.assertEqual('1', tmp)
        tmp = get_config_value(interface, 'he_su_beamformee')
        self.assertEqual('1', tmp)
        tmp = get_config_value(interface, 'he_mu_beamformer')
        self.assertEqual('1', tmp)

        # Check for running process
        self.assertTrue(process_named_running('hostapd'))

    def test_wireless_hostapd_he_6ghz_config(self):
        # Only set the hostapd (access-point) options - HE mode for 802.11ax at 6GHz
        interface = self._interfaces[1] # wlan1
        ssid = 'ssid'
        channel = '1'
        sae_pw = 'VyOSVyOSVyOS'
        bss_color = '37'
        channel_set_width = '134'
        center_channel_freq_1 = '15'

        self.cli_set(self._base_path + [interface, 'ssid', ssid])
        self.cli_set(self._base_path + [interface, 'type', 'access-point'])
        self.cli_set(self._base_path + [interface, 'channel', channel])
        self.cli_set(self._base_path + [interface, 'mode', 'ax'])
        self.cli_set(self._base_path + [interface, 'security', 'wpa', 'mode', 'wpa3'])
        self.cli_set(self._base_path + [interface, 'security', 'wpa', 'passphrase', sae_pw])
        self.cli_set(self._base_path + [interface, 'security', 'wpa', 'cipher', 'CCMP'])
        self.cli_set(self._base_path + [interface, 'security', 'wpa', 'cipher', 'GCMP'])
        self.cli_set(self._base_path + [interface, 'enable-bf-protection'])
        self.cli_set(self._base_path + [interface, 'mgmt-frame-protection', 'required'])
        self.cli_set(self._base_path + [interface, 'capabilities', 'he', 'bss-color', bss_color])
        self.cli_set(self._base_path + [interface, 'capabilities', 'he', 'channel-set-width', channel_set_width])
        self.cli_set(self._base_path + [interface, 'capabilities', 'he', 'center-channel-freq', 'freq-1', center_channel_freq_1])
        self.cli_set(self._base_path + [interface, 'capabilities', 'he', 'antenna-pattern-fixed'])
        self.cli_set(self._base_path + [interface, 'capabilities', 'he', 'beamform', 'multi-user-beamformer'])
        self.cli_set(self._base_path + [interface, 'capabilities', 'he', 'beamform', 'single-user-beamformer'])

        self.cli_commit()

        #
        # Validate Config
        #
        tmp = get_config_value(interface, 'interface')
        self.assertEqual(interface, tmp)

        # ssid
        tmp = get_config_value(interface, 'ssid')
        self.assertEqual(ssid, tmp)

        # mode of operation resulting from [interface, 'mode', 'ax']
        tmp = get_config_value(interface, 'hw_mode')
        self.assertEqual('a', tmp)
        tmp = get_config_value(interface, 'ieee80211h')
        self.assertEqual('1', tmp)
        tmp = get_config_value(interface, 'ieee80211ax')
        self.assertEqual('1', tmp)

        # channel and channel width
        tmp = get_config_value(interface, 'channel')
        self.assertEqual(channel, tmp)
        tmp = get_config_value(interface, 'op_class')
        self.assertEqual(channel_set_width, tmp)
        tmp = get_config_value(interface, 'he_oper_centr_freq_seg0_idx')
        self.assertEqual(center_channel_freq_1, tmp)

        # BSS coloring
        tmp = get_config_value(interface, 'he_bss_color')
        self.assertEqual(bss_color, tmp)

        # sae_password
        tmp = get_config_value(interface, 'sae_password')
        self.assertEqual(sae_pw, tmp)

        # WPA3 and dependencies
        tmp = get_config_value(interface, 'wpa')
        self.assertEqual('2', tmp)
        tmp = get_config_value(interface, 'rsn_pairwise')
        self.assertEqual('CCMP GCMP', tmp)
        tmp = get_config_value(interface, 'wpa_key_mgmt')
        self.assertEqual('SAE', tmp)

        # antenna pattern
        tmp = get_config_value(interface, 'he_6ghz_rx_ant_pat')
        self.assertEqual('1', tmp)

        # beamforming
        tmp = get_config_value(interface, 'he_mu_beamformer')
        self.assertEqual('1', tmp)
        tmp = get_config_value(interface, 'he_su_beamformee')
        self.assertEqual('0', tmp)
        tmp = get_config_value(interface, 'he_mu_beamformer')
        self.assertEqual('1', tmp)

        # Check for running process
        self.assertTrue(process_named_running('hostapd'))

    def test_wireless_hostapd_wpa_config(self):
        # Only set the hostapd (access-point) options
        interface = self._interfaces[1] # wlan1
        ssid = 'VyOS-SMOKETEST'
        channel = '1'
        wpa_key = 'VyOSVyOSVyOS'
        mode = 'n'

        self.cli_set(self._base_path + [interface, 'type', 'access-point'])
        self.cli_set(self._base_path + [interface, 'mode', mode])

        # SSID and country-code are already configured in self.setUpClass()
        # Therefore, we must delete those here to check if commit will fail without it.
        self.cli_delete(wifi_cc_path)
        self.cli_delete(self._base_path + [interface, 'ssid'])

        # Country-Code must be set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(wifi_cc_path + [country])

        # SSID must be set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(self._base_path + [interface, 'ssid', ssid])

        # Channel must be set (defaults to channel 0)
        self.cli_set(self._base_path + [interface, 'channel', channel])

        self.cli_set(self._base_path + [interface, 'security', 'wpa', 'mode', 'wpa2'])
        self.cli_set(self._base_path + [interface, 'security', 'wpa', 'passphrase', wpa_key])

        self.cli_commit()

        #
        # Validate Config
        #
        tmp = get_config_value(interface, 'interface')
        self.assertEqual(interface, tmp)

        tmp = get_config_value(interface, 'hw_mode')
        # rewrite special mode
        if mode == 'n': mode = 'g'
        self.assertEqual(mode, tmp)

        # WPA key
        tmp = get_config_value(interface, 'wpa')
        self.assertEqual('2', tmp)
        tmp = get_config_value(interface, 'wpa_passphrase')
        self.assertEqual(wpa_key, tmp)

        # SSID
        tmp = get_config_value(interface, 'ssid')
        self.assertEqual(ssid, tmp)

        # channel
        tmp = get_config_value(interface, 'channel')
        self.assertEqual(channel, tmp)

        # Country code
        tmp = get_config_value(interface, 'country_code')
        self.assertEqual(country.upper(), tmp)

        # Check for running process
        self.assertTrue(process_named_running('hostapd'))

    def test_wireless_access_point_bridge(self):
        interface = self._interfaces[1] # wlan1
        ssid = 'VyOS-Test'
        bridge = 'br42477'

        # We need a bridge where we can hook our access-point interface to
        bridge_path = ['interfaces', 'bridge', bridge]
        self.cli_set(bridge_path + ['member', 'interface', interface])

        self.cli_set(self._base_path + [interface, 'ssid', ssid])
        self.cli_set(self._base_path + [interface, 'type', 'access-point'])
        self.cli_set(self._base_path + [interface, 'channel', '1'])

        self.cli_commit()

        # Check for running process
        self.assertTrue(process_named_running('hostapd'))

        bridge_members = []
        for tmp in glob(f'/sys/class/net/{bridge}/lower_*'):
            bridge_members.append(os.path.basename(tmp).replace('lower_', ''))

        self.assertIn(interface, bridge_members)

        # Now generate a VLAN on the bridge
        self.cli_set(bridge_path + ['enable-vlan'])
        self.cli_set(bridge_path + ['vif', '20', 'address', '10.0.0.1/24'])

        self.cli_commit()

        tmp = get_config_value(interface, 'bridge')
        self.assertEqual(tmp, bridge)
        tmp = get_config_value(interface, 'wds_sta')
        self.assertEqual(tmp, '1')

        self.cli_delete(bridge_path)

    def test_wireless_security_station_address(self):
        interface = self._interfaces[1] # wlan1
        ssid = 'VyOS-ACL'

        hostapd_accept_station_conf = f'/run/hostapd/{interface}_station_accept.conf'
        hostapd_deny_station_conf = f'/run/hostapd/{interface}_station_deny.conf'

        accept_mac = ['00:00:00:00:ac:01', '00:00:00:00:ac:02', '00:00:00:00:ac:03', '00:00:00:00:ac:04']
        deny_mac = ['00:00:00:00:de:01', '00:00:00:00:de:02', '00:00:00:00:de:03', '00:00:00:00:de:04']

        self.cli_set(self._base_path + [interface, 'ssid', ssid])
        self.cli_set(self._base_path + [interface, 'type', 'access-point'])
        self.cli_set(self._base_path + [interface, 'security', 'station-address', 'mode', 'accept'])

        for mac in accept_mac:
            self.cli_set(self._base_path + [interface, 'security', 'station-address', 'accept', 'mac', mac])
        for mac in deny_mac:
            self.cli_set(self._base_path + [interface, 'security', 'station-address', 'deny', 'mac', mac])

        self.cli_commit()

        self.assertTrue(interface_exists(interface))
        self.assertTrue(os.path.isfile(f'/run/hostapd/{interface}_station_accept.conf'))
        self.assertTrue(os.path.isfile(f'/run/hostapd/{interface}_station_deny.conf'))

        self.assertTrue(process_named_running('hostapd'))

        # in accept mode all addresses are allowed unless specified in the deny list
        tmp = get_config_value(interface, 'macaddr_acl')
        self.assertEqual(tmp, '0')

        accept_list = read_file(hostapd_accept_station_conf)
        for mac in accept_mac:
            self.assertIn(mac, accept_list)

        deny_list = read_file(hostapd_deny_station_conf)
        for mac in deny_mac:
            self.assertIn(mac, deny_list)

        #  Switch mode accept -> deny
        self.cli_set(self._base_path + [interface, 'security', 'station-address', 'mode', 'deny'])
        self.cli_commit()

        self.assertTrue(interface_exists(interface))
        self.assertTrue(os.path.isfile(f'/run/hostapd/{interface}_station_accept.conf'))
        self.assertTrue(os.path.isfile(f'/run/hostapd/{interface}_station_deny.conf'))

        # In deny mode all addresses are denied unless specified in the allow list
        tmp = get_config_value(interface, 'macaddr_acl')
        self.assertEqual(tmp, '1')

        # Check for running process
        self.assertTrue(process_named_running('hostapd'))

if __name__ == '__main__':
    check_kmod('mac80211_hwsim')
    # loading the module created two WIFI Interfaces in the background (wlan0 and wlan1)
    # remove them to have a clean test start
    for interface in ['wlan0', 'wlan1']:
        if interface_exists(interface):
            call(f'sudo iw dev {interface} del')
    unittest.main(verbosity=2)
