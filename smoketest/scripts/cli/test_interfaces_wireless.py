#!/usr/bin/env python3
#
# Copyright (C) 2020-2023 VyOS maintainers and contributors
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
from vyos.utils.process import process_named_running
from vyos.utils.kernel import check_kmod
from vyos.utils.file import read_file
from vyos.xml_ref import default_value

def get_config_value(interface, key):
    tmp = read_file(f'/run/hostapd/{interface}.conf')
    tmp = re.findall(f'{key}=+(.*)', tmp)
    return tmp[0]

class WirelessInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['interfaces', 'wireless']
        cls._options = {
            'wlan0':  ['physical-device phy0', 'ssid VyOS-WIFI-0',
                       'type station', 'address 192.0.2.1/30'],
            'wlan1':  ['physical-device phy0', 'ssid VyOS-WIFI-1', 'country-code se',
                       'type access-point', 'address 192.0.2.5/30', 'channel 0'],
            'wlan10': ['physical-device phy1', 'ssid VyOS-WIFI-2',
                       'type station', 'address 192.0.2.9/30'],
            'wlan11': ['physical-device phy1', 'ssid VyOS-WIFI-3', 'country-code se',
                       'type access-point', 'address 192.0.2.13/30', 'channel 0'],
        }
        cls._interfaces = list(cls._options)
        # call base-classes classmethod
        super(WirelessInterfaceTest, cls).setUpClass()

        # T5245 - currently testcases are disabled
        cls._test_ipv6 = False
        cls._test_vlan = False

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
        interface = 'wlan0'
        ssid = 'ssid'

        self.cli_set(self._base_path + [interface, 'ssid', ssid])
        self.cli_set(self._base_path + [interface, 'country-code', 'se'])
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

    def test_wireless_hostapd_wpa_config(self):
        # Only set the hostapd (access-point) options
        interface = 'wlan0'
        phy = 'phy0'
        ssid = 'ssid'
        channel = '1'
        wpa_key = 'VyOSVyOSVyOS'
        mode = 'n'
        country = 'de'

        self.cli_set(self._base_path + [interface, 'physical-device', phy])
        self.cli_set(self._base_path + [interface, 'type', 'access-point'])
        self.cli_set(self._base_path + [interface, 'mode', mode])

        # SSID must be set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(self._base_path + [interface, 'ssid', ssid])

        # Channel must be set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(self._base_path + [interface, 'channel', channel])

        # Country-Code must be set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(self._base_path + [interface, 'country-code', country])

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
        interface = 'wlan0'
        ssid = 'VyOS-Test'
        bridge = 'br42477'

        # We need a bridge where we can hook our access-point interface to
        bridge_path = ['interfaces', 'bridge', bridge]
        self.cli_set(bridge_path + ['member', 'interface', interface])

        self.cli_set(self._base_path + [interface, 'ssid', ssid])
        self.cli_set(self._base_path + [interface, 'country-code', 'se'])
        self.cli_set(self._base_path + [interface, 'type', 'access-point'])

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
        interface = 'wlan0'
        ssid = 'VyOS-ACL'

        hostapd_accept_station_conf = f'/run/hostapd/{interface}_station_accept.conf'
        hostapd_deny_station_conf = f'/run/hostapd/{interface}_station_deny.conf'

        accept_mac = ['00:00:00:00:ac:01', '00:00:00:00:ac:02', '00:00:00:00:ac:03', '00:00:00:00:ac:04']
        deny_mac = ['00:00:00:00:de:01', '00:00:00:00:de:02', '00:00:00:00:de:03', '00:00:00:00:de:04']

        self.cli_set(self._base_path + [interface, 'ssid', ssid])
        self.cli_set(self._base_path + [interface, 'country-code', 'se'])
        self.cli_set(self._base_path + [interface, 'type', 'access-point'])
        self.cli_set(self._base_path + [interface, 'security', 'station-address', 'mode', 'accept'])

        for mac in accept_mac:
            self.cli_set(self._base_path + [interface, 'security', 'station-address', 'accept', 'mac', mac])
        for mac in deny_mac:
            self.cli_set(self._base_path + [interface, 'security', 'station-address', 'deny', 'mac', mac])

        self.cli_commit()

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
        # In deny mode all addresses are denied unless specified in the allow list
        tmp = get_config_value(interface, 'macaddr_acl')
        self.assertEqual(tmp, '1')

        # Check for running process
        self.assertTrue(process_named_running('hostapd'))

if __name__ == '__main__':
    check_kmod('mac80211_hwsim')
    unittest.main(verbosity=2)
