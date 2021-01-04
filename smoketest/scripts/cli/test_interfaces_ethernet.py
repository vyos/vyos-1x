#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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
from vyos.ifconfig import Section
from vyos.util import cmd
from vyos.util import process_named_running
from vyos.util import read_file

ca_cert  = '/config/auth/eapol_test_ca.pem'
ssl_cert = '/config/auth/eapol_test_server.pem'
ssl_key  = '/config/auth/eapol_test_server.key'

def get_wpa_supplicant_value(interface, key):
    tmp = read_file(f'/run/wpa_supplicant/{interface}.conf')
    tmp = re.findall(r'\n?{}=(.*)'.format(key), tmp)
    return tmp[0]

class EthernetInterfaceTest(BasicInterfaceTest.BaseTest):
    def setUp(self):
        super().setUp()

        self._base_path = ['interfaces', 'ethernet']
        self._mirror_interfaces = ['dum10100']
        self._test_ip = True
        self._test_mtu = True
        self._test_vlan = True
        self._test_qinq = True
        self._test_ipv6 = True
        self._test_mirror = True
        self._interfaces = []

        # we need to filter out VLAN interfaces identified by a dot (.)
        # in their name - just in case!
        if 'TEST_ETH' in os.environ:
            tmp = os.environ['TEST_ETH'].split()
            self._interfaces = tmp
        else:
            for tmp in Section.interfaces("ethernet"):
                if not '.' in tmp:
                    self._interfaces.append(tmp)

        self._macs = {}
        for interface in self._interfaces:
            try:
                mac = self.session.show_config(self._base_path +
                                               [interface, 'hw-id']).split()[1]
            except:
                # during initial system startup there is no hw-id node
                mac = read_file(f'/sys/class/net/{interface}/address')
            self._macs[interface] = mac

        # Creating test interfaces for port mirroring
        for mon_intf in self._mirror_interfaces:
            if 'dum' in mon_intf:
                self.session.set(['interfaces', 'dummy', mon_intf])


    def tearDown(self):
        for interface in self._interfaces:
            # when using a dedicated interface to test via TEST_ETH environment
            # variable only this one will be cleared in the end - usable to test
            # ethernet interfaces via SSH
            self.session.delete(self._base_path + [interface])
            self.session.set(self._base_path + [interface, 'duplex', 'auto'])
            self.session.set(self._base_path + [interface, 'speed', 'auto'])
            self.session.set(self._base_path + [interface, 'hw-id', self._macs[interface]])
        
        # Delete the dependent interface of port mirroring
        for mon_intf in self._mirror_interfaces:
            if 'dum' in mon_intf:
                self.session.delete(['interfaces', 'dummy', mon_intf])

        super().tearDown()


    def test_dhcp_disable_interface(self):
        # When interface is configured as admin down, it must be admin down
        # even when dhcpc starts on the given interface
        for interface in self._interfaces:
            self.session.set(self._base_path + [interface, 'disable'])

            # Also enable DHCP (ISC DHCP always places interface in admin up
            # state so we check that we do not start DHCP client.
            # https://phabricator.vyos.net/T2767
            self.session.set(self._base_path + [interface, 'address', 'dhcp'])

        self.session.commit()

        # Validate interface state
        for interface in self._interfaces:
            with open(f'/sys/class/net/{interface}/flags', 'r') as f:
                flags = f.read()
            self.assertEqual(int(flags, 16) & 1, 0)

    def test_offloading_rps(self):
        # enable RPS on all available CPUs, RPS works woth a CPU bitmask,
        # where each bit represents a CPU (core/thread). The formula below
        # expands to rps_cpus = 255 for a 8 core system
        rps_cpus = (1 << os.cpu_count()) -1

        # XXX: we should probably reserve one core when the system is under
        # high preasure so we can still have a core left for housekeeping.
        # This is done by masking out the lowst bit so CPU0 is spared from
        # receive packet steering.
        rps_cpus &= ~1

        for interface in self._interfaces:
            self.session.set(self._base_path + [interface, 'offload', 'rps'])

        self.session.commit()

        for interface in self._interfaces:
            cpus = read_file('/sys/class/net/eth1/queues/rx-0/rps_cpus')
            # remove the nasty ',' separation on larger strings
            cpus = cpus.replace(',','')
            cpus = int(cpus, 16)

            self.assertEqual(f'{cpus:x}', f'{rps_cpus:x}')


    def test_eapol_support(self):
        for interface in self._interfaces:
            # Enable EAPoL
            self.session.set(self._base_path + [interface, 'eapol', 'ca-cert-file', ca_cert])
            self.session.set(self._base_path + [interface, 'eapol', 'cert-file', ssl_cert])
            self.session.set(self._base_path + [interface, 'eapol', 'key-file', ssl_key])

        self.session.commit()

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
            self.assertEqual(f'"{ca_cert}"', tmp)

            tmp = get_wpa_supplicant_value(interface, 'client_cert')
            self.assertEqual(f'"{ssl_cert}"', tmp)

            tmp = get_wpa_supplicant_value(interface, 'private_key')
            self.assertEqual(f'"{ssl_key}"', tmp)

            mac = read_file(f'/sys/class/net/{interface}/address')
            tmp = get_wpa_supplicant_value(interface, 'identity')
            self.assertEqual(f'"{mac}"', tmp)

if __name__ == '__main__':
    # Our SSL certificates need a subject ...
    subject = '/C=DE/ST=BY/O=VyOS/localityName=Cloud/commonName=vyos/' \
              'organizationalUnitName=VyOS/emailAddress=maintainers@vyos.io/'

    if not (os.path.isfile(ssl_key) and os.path.isfile(ssl_cert)):
        # Generate mandatory SSL certificate
        tmp = f'openssl req -newkey rsa:4096 -new -nodes -x509 -days 3650 '\
              f'-keyout {ssl_key} -out {ssl_cert} -subj {subject}'
        print(cmd(tmp))

    if not os.path.isfile(ca_cert):
        # Generate "CA"
        tmp = f'openssl req -new -x509 -key {ssl_key} -out {ca_cert} -subj {subject}'
        print(cmd(tmp))

    for file in [ca_cert, ssl_cert, ssl_key]:
        cmd(f'sudo chown radius_priv_user:vyattacfg {file}')

    unittest.main(verbosity=2)
