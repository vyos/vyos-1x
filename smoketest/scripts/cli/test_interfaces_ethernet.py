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

from glob import glob
from json import loads

from netifaces import AF_INET
from netifaces import AF_INET6
from netifaces import ifaddresses

from base_interfaces_test import BasicInterfaceTest
from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Section
from vyos.pki import CERT_BEGIN
from vyos.utils.process import cmd
from vyos.utils.process import process_named_running
from vyos.utils.process import popen
from vyos.utils.file import read_file
from vyos.utils.network import is_ipv6_link_local

server_ca_root_cert_data = """
MIIBcTCCARagAwIBAgIUDcAf1oIQV+6WRaW7NPcSnECQ/lUwCgYIKoZIzj0EAwIw
HjEcMBoGA1UEAwwTVnlPUyBzZXJ2ZXIgcm9vdCBDQTAeFw0yMjAyMTcxOTQxMjBa
Fw0zMjAyMTUxOTQxMjBaMB4xHDAaBgNVBAMME1Z5T1Mgc2VydmVyIHJvb3QgQ0Ew
WTATBgcqhkjOPQIBBggqhkjOPQMBBwNCAAQ0y24GzKQf4aM2Ir12tI9yITOIzAUj
ZXyJeCmYI6uAnyAMqc4Q4NKyfq3nBi4XP87cs1jlC1P2BZ8MsjL5MdGWozIwMDAP
BgNVHRMBAf8EBTADAQH/MB0GA1UdDgQWBBRwC/YaieMEnjhYa7K3Flw/o0SFuzAK
BggqhkjOPQQDAgNJADBGAiEAh3qEj8vScsjAdBy5shXzXDVVOKWCPTdGrPKnu8UW
a2cCIQDlDgkzWmn5ujc5ATKz1fj+Se/aeqwh4QyoWCVTFLIxhQ==
"""

server_ca_intermediate_cert_data = """
MIIBmTCCAT+gAwIBAgIUNzrtHzLmi3QpPK57tUgCnJZhXXQwCgYIKoZIzj0EAwIw
HjEcMBoGA1UEAwwTVnlPUyBzZXJ2ZXIgcm9vdCBDQTAeFw0yMjAyMTcxOTQxMjFa
Fw0zMjAyMTUxOTQxMjFaMCYxJDAiBgNVBAMMG1Z5T1Mgc2VydmVyIGludGVybWVk
aWF0ZSBDQTBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABEl2nJ1CzoqPV6hWII2m
eGN/uieU6wDMECTk/LgG8CCCSYb488dibUiFN/1UFsmoLIdIhkx/6MUCYh62m8U2
WNujUzBRMA8GA1UdEwEB/wQFMAMBAf8wHQYDVR0OBBYEFMV3YwH88I5gFsFUibbQ
kMR0ECPsMB8GA1UdIwQYMBaAFHAL9hqJ4wSeOFhrsrcWXD+jRIW7MAoGCCqGSM49
BAMCA0gAMEUCIQC/ahujD9dp5pMMCd3SZddqGC9cXtOwMN0JR3e5CxP13AIgIMQm
jMYrinFoInxmX64HfshYqnUY8608nK9D2BNPOHo=
"""

client_ca_root_cert_data = """
MIIBcDCCARagAwIBAgIUZmoW2xVdwkZSvglnkCq0AHKa6zIwCgYIKoZIzj0EAwIw
HjEcMBoGA1UEAwwTVnlPUyBjbGllbnQgcm9vdCBDQTAeFw0yMjAyMTcxOTQxMjFa
Fw0zMjAyMTUxOTQxMjFaMB4xHDAaBgNVBAMME1Z5T1MgY2xpZW50IHJvb3QgQ0Ew
WTATBgcqhkjOPQIBBggqhkjOPQMBBwNCAATUpKXzQk2NOVKDN4VULk2yw4mOKPvn
mg947+VY7lbpfOfAUD0QRg95qZWCw899eKnXp/U4TkAVrmEKhUb6OJTFozIwMDAP
BgNVHRMBAf8EBTADAQH/MB0GA1UdDgQWBBTXu6xGWUl25X3sBtrhm3BJSICIATAK
BggqhkjOPQQDAgNIADBFAiEAnTzEwuTI9bz2Oae3LZbjP6f/f50KFJtjLZFDbQz7
DpYCIDNRHV8zBUibC+zg5PqMpQBKd/oPfNU76nEv6xkp/ijO
"""

client_ca_intermediate_cert_data = """
MIIBmDCCAT+gAwIBAgIUJEMdotgqA7wU4XXJvEzDulUAGqgwCgYIKoZIzj0EAwIw
HjEcMBoGA1UEAwwTVnlPUyBjbGllbnQgcm9vdCBDQTAeFw0yMjAyMTcxOTQxMjJa
Fw0zMjAyMTUxOTQxMjJaMCYxJDAiBgNVBAMMG1Z5T1MgY2xpZW50IGludGVybWVk
aWF0ZSBDQTBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABGyIVIi217s9j3O+WQ2b
6R65/Z0ZjQpELxPjBRc0CA0GFCo+pI5EvwI+jNFArvTAJ5+ZdEWUJ1DQhBKDDQdI
avCjUzBRMA8GA1UdEwEB/wQFMAMBAf8wHQYDVR0OBBYEFOUS8oNJjChB1Rb9Blcl
ETvziHJ9MB8GA1UdIwQYMBaAFNe7rEZZSXblfewG2uGbcElIgIgBMAoGCCqGSM49
BAMCA0cAMEQCIArhaxWgRsAUbEeNHD/ULtstLHxw/P97qPUSROLQld53AiBjgiiz
9pDfISmpekZYz6bIDWRIR0cXUToZEMFNzNMrQg==
"""

client_cert_data = """
MIIBmTCCAUCgAwIBAgIUV5T77XdE/tV82Tk4Vzhp5BIFFm0wCgYIKoZIzj0EAwIw
JjEkMCIGA1UEAwwbVnlPUyBjbGllbnQgaW50ZXJtZWRpYXRlIENBMB4XDTIyMDIx
NzE5NDEyMloXDTMyMDIxNTE5NDEyMlowIjEgMB4GA1UEAwwXVnlPUyBjbGllbnQg
Y2VydGlmaWNhdGUwWTATBgcqhkjOPQIBBggqhkjOPQMBBwNCAARuyynqfc/qJj5e
KJ03oOH8X4Z8spDeAPO9WYckMM0ldPj+9kU607szFzPwjaPWzPdgyIWz3hcN8yAh
CIhytmJao1AwTjAMBgNVHRMBAf8EAjAAMB0GA1UdDgQWBBTIFKrxZ+PqOhYSUqnl
TGCUmM7wTjAfBgNVHSMEGDAWgBTlEvKDSYwoQdUW/QZXJRE784hyfTAKBggqhkjO
PQQDAgNHADBEAiAvO8/jvz05xqmP3OXD53XhfxDLMIxzN4KPoCkFqvjlhQIgIHq2
/geVx3rAOtSps56q/jiDouN/aw01TdpmGKVAa9U=
"""

client_key_data = """
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgxaxAQsJwjoOCByQE
+qSYKtKtJzbdbOnTsKNSrfgkFH6hRANCAARuyynqfc/qJj5eKJ03oOH8X4Z8spDe
APO9WYckMM0ldPj+9kU607szFzPwjaPWzPdgyIWz3hcN8yAhCIhytmJa
"""

def get_wpa_supplicant_value(interface, key):
    tmp = read_file(f'/run/wpa_supplicant/{interface}.conf')
    tmp = re.findall(r'\n?{}=(.*)'.format(key), tmp)
    return tmp[0]

def get_certificate_count(interface, cert_type):
    tmp = read_file(f'/run/wpa_supplicant/{interface}_{cert_type}.pem')
    return tmp.count(CERT_BEGIN)

class EthernetInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['interfaces', 'ethernet']
        cls._mirror_interfaces = ['dum21354']

        # We only test on physical interfaces and not VLAN (sub-)interfaces
        if 'TEST_ETH' in os.environ:
            tmp = os.environ['TEST_ETH'].split()
            cls._interfaces = tmp
        else:
            for tmp in Section.interfaces('ethernet', vlan=False):
                cls._interfaces.append(tmp)

        cls._macs = {}
        for interface in cls._interfaces:
            cls._macs[interface] = read_file(f'/sys/class/net/{interface}/address')

        # call base-classes classmethod
        super(EthernetInterfaceTest, cls).setUpClass()

    def tearDown(self):
        for interface in self._interfaces:
            # when using a dedicated interface to test via TEST_ETH environment
            # variable only this one will be cleared in the end - usable to test
            # ethernet interfaces via SSH
            self.cli_delete(self._base_path + [interface])
            self.cli_set(self._base_path + [interface, 'duplex', 'auto'])
            self.cli_set(self._base_path + [interface, 'speed', 'auto'])
            self.cli_set(self._base_path + [interface, 'hw-id', self._macs[interface]])

        self.cli_commit()

        # Verify that no address remains on the system as this is an eternal
        # interface.
        for interface in self._interfaces:
            self.assertNotIn(AF_INET, ifaddresses(interface))
            # required for IPv6 link-local address
            self.assertIn(AF_INET6, ifaddresses(interface))
            for addr in ifaddresses(interface)[AF_INET6]:
                # checking link local addresses makes no sense
                if is_ipv6_link_local(addr['addr']):
                    continue
                self.assertFalse(is_intf_addr_assigned(interface, addr['addr']))
            # Ensure no VLAN interfaces are left behind
            tmp = [x for x in Section.interfaces('ethernet') if x.startswith(f'{interface}.')]
            self.assertListEqual(tmp, [])

    def test_offloading_rps(self):
        # enable RPS on all available CPUs, RPS works with a CPU bitmask,
        # where each bit represents a CPU (core/thread). The formula below
        # expands to rps_cpus = 255 for a 8 core system
        rps_cpus = (1 << os.cpu_count()) -1

        # XXX: we should probably reserve one core when the system is under
        # high preasure so we can still have a core left for housekeeping.
        # This is done by masking out the lowst bit so CPU0 is spared from
        # receive packet steering.
        rps_cpus &= ~1

        for interface in self._interfaces:
            self.cli_set(self._base_path + [interface, 'offload', 'rps'])

        self.cli_commit()

        for interface in self._interfaces:
            cpus = read_file(f'/sys/class/net/{interface}/queues/rx-0/rps_cpus')
            # remove the nasty ',' separation on larger strings
            cpus = cpus.replace(',','')
            cpus = int(cpus, 16)

            self.assertEqual(f'{cpus:x}', f'{rps_cpus:x}')

    def test_offloading_rfs(self):
        global_rfs_flow = 32768
        rfs_flow = global_rfs_flow

        for interface in self._interfaces:
            self.cli_set(self._base_path + [interface, 'offload', 'rfs'])

        self.cli_commit()

        for interface in self._interfaces:
            queues = len(glob(f'/sys/class/net/{interface}/queues/rx-*'))
            rfs_flow = int(global_rfs_flow/queues)
            for i in range(0, queues):
                tmp = read_file(f'/sys/class/net/{interface}/queues/rx-{i}/rps_flow_cnt')
                self.assertEqual(int(tmp), rfs_flow)

        tmp = read_file(f'/proc/sys/net/core/rps_sock_flow_entries')
        self.assertEqual(int(tmp), global_rfs_flow)

        # delete configuration of RFS and check all values returned to default "0"
        for interface in self._interfaces:
            self.cli_delete(self._base_path + [interface, 'offload', 'rfs'])

        self.cli_commit()

        for interface in self._interfaces:
            queues = len(glob(f'/sys/class/net/{interface}/queues/rx-*'))
            rfs_flow = int(global_rfs_flow/queues)
            for i in range(0, queues):
                tmp = read_file(f'/sys/class/net/{interface}/queues/rx-{i}/rps_flow_cnt')
                self.assertEqual(int(tmp), 0)


    def test_non_existing_interface(self):
        unknonw_interface = self._base_path + ['eth667']
        self.cli_set(unknonw_interface)

        # check validate() - interface does not exist
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # we need to remove this wrong interface from the configuration
        # manually, else tearDown() will have problem in commit()
        self.cli_delete(unknonw_interface)

    def test_speed_duplex_verify(self):
        for interface in self._interfaces:
            self.cli_set(self._base_path + [interface, 'speed', '1000'])

            # check validate() - if either speed or duplex is not auto, the
            # other one must be manually configured, too
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_set(self._base_path + [interface, 'speed', 'auto'])
            self.cli_commit()

    def test_eapol_support(self):
        ca_certs = {
            'eapol-server-ca-root': server_ca_root_cert_data,
            'eapol-server-ca-intermediate': server_ca_intermediate_cert_data,
            'eapol-client-ca-root': client_ca_root_cert_data,
            'eapol-client-ca-intermediate': client_ca_intermediate_cert_data,
        }
        cert_name = 'eapol-client'

        for name, data in ca_certs.items():
            self.cli_set(['pki', 'ca', name, 'certificate', data.replace('\n','')])

        self.cli_set(['pki', 'certificate', cert_name, 'certificate', client_cert_data.replace('\n','')])
        self.cli_set(['pki', 'certificate', cert_name, 'private', 'key', client_key_data.replace('\n','')])

        for interface in self._interfaces:
            # Enable EAPoL
            self.cli_set(self._base_path + [interface, 'eapol', 'ca-certificate', 'eapol-server-ca-intermediate'])
            self.cli_set(self._base_path + [interface, 'eapol', 'ca-certificate', 'eapol-client-ca-intermediate'])
            self.cli_set(self._base_path + [interface, 'eapol', 'certificate', cert_name])

        self.cli_commit()

        # Test multiple CA chains
        self.assertEqual(get_certificate_count(interface, 'ca'), 4)

        for interface in self._interfaces:
            self.cli_delete(self._base_path + [interface, 'eapol', 'ca-certificate', 'eapol-client-ca-intermediate'])

        self.cli_commit()

        # Check for running process
        self.assertTrue(process_named_running('wpa_supplicant'))

        # Validate interface config
        for interface in self._interfaces:
            tmp = get_wpa_supplicant_value(interface, 'key_mgmt')
            self.assertEqual('IEEE8021X', tmp)

            tmp = get_wpa_supplicant_value(interface, 'eap')
            self.assertEqual('TLS', tmp)

            tmp = get_wpa_supplicant_value(interface, 'eapol_flags')
            self.assertEqual('0', tmp)

            tmp = get_wpa_supplicant_value(interface, 'ca_cert')
            self.assertEqual(f'"/run/wpa_supplicant/{interface}_ca.pem"', tmp)

            tmp = get_wpa_supplicant_value(interface, 'client_cert')
            self.assertEqual(f'"/run/wpa_supplicant/{interface}_cert.pem"', tmp)

            tmp = get_wpa_supplicant_value(interface, 'private_key')
            self.assertEqual(f'"/run/wpa_supplicant/{interface}_cert.key"', tmp)

            mac = read_file(f'/sys/class/net/{interface}/address')
            tmp = get_wpa_supplicant_value(interface, 'identity')
            self.assertEqual(f'"{mac}"', tmp)

        # Check certificate files have the full chain
        self.assertEqual(get_certificate_count(interface, 'ca'), 2)
        self.assertEqual(get_certificate_count(interface, 'cert'), 3)

        for name in ca_certs:
            self.cli_delete(['pki', 'ca', name])
        self.cli_delete(['pki', 'certificate', cert_name])

    def test_ethtool_ring_buffer(self):
        for interface in self._interfaces:
            # We do not use vyos.ethtool here to not have any chance
            # for invalid testcases. Re-gain data by hand
            tmp = cmd(f'sudo ethtool --json --show-ring {interface}')
            tmp = loads(tmp)
            max_rx = str(tmp[0]['rx-max'])
            max_tx = str(tmp[0]['tx-max'])

            self.cli_set(self._base_path + [interface, 'ring-buffer', 'rx', max_rx])
            self.cli_set(self._base_path + [interface, 'ring-buffer', 'tx', max_tx])

        self.cli_commit()

        for interface in self._interfaces:
            tmp = cmd(f'sudo ethtool --json --show-ring {interface}')
            tmp = loads(tmp)
            max_rx = str(tmp[0]['rx-max'])
            max_tx = str(tmp[0]['tx-max'])
            rx = str(tmp[0]['rx'])
            tx = str(tmp[0]['tx'])

            # validate if the above change was carried out properly and the
            # ring-buffer size got increased
            self.assertEqual(max_rx, rx)
            self.assertEqual(max_tx, tx)

    def test_ethtool_flow_control(self):
        for interface in self._interfaces:
            # Disable flow-control
            self.cli_set(self._base_path + [interface, 'disable-flow-control'])
            # Check current flow-control state on ethernet interface
            out, err = popen(f'sudo ethtool --json --show-pause {interface}')
            # Flow-control not supported - test if it bails out with a proper
            # this is a dynamic path where err = 1 on VMware, but err = 0 on
            # a physical box.
            if bool(err):
                with self.assertRaises(ConfigSessionError):
                    self.cli_commit()
            else:
                out = loads(out)
                # Flow control is on
                self.assertTrue(out[0]['autonegotiate'])

                # commit change on CLI to disable-flow-control and re-test
                self.cli_commit()

                out, err = popen(f'sudo ethtool --json --show-pause {interface}')
                out = loads(out)
                self.assertFalse(out[0]['autonegotiate'])

    def test_ethtool_evpn_uplink_tarcking(self):
        for interface in self._interfaces:
            self.cli_set(self._base_path + [interface, 'evpn', 'uplink'])

        self.cli_commit()

        for interface in self._interfaces:
            frrconfig = self.getFRRconfig(f'interface {interface}', daemon='zebra')
            self.assertIn(f' evpn mh uplink', frrconfig)

if __name__ == '__main__':
    unittest.main(verbosity=2)
