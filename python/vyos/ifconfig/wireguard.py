# Copyright 2019 VyOS maintainers and contributors <maintainers@vyos.io>
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
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.


import os

import vyos
from vyos.ifconfig.interface import Interface
from datetime import timedelta

class WireGuardIf(Interface):
    options = ['port', 'private-key', 'pubkey', 'psk',
               'allowed-ips', 'fwmark', 'endpoint', 'keepalive']

    default = {
        'type': 'wireguard',
        'port': 0,
        'private-key': None,
        'pubkey': None,
        'psk': '/dev/null',
        'allowed-ips': [],
        'fwmark': 0x00,
        'endpoint': None,
        'keepalive': 0
    }

    """
    Wireguard interface class, contains a comnfig dictionary since
    wireguard VPN is being comnfigured via the wg command rather than
    writing the config into a file. Otherwise if a pre-shared key is used
    (symetric enryption key), it would we exposed within multiple files.
    Currently it's only within the config.boot if the config was saved.

    Example:
    >>> from vyos.ifconfig import WireGuardIf as wg_if
    >>> wg_intfc = wg_if("wg01")
    >>> print (wg_intfc.wg_config)
    {'private-key': None, 'keepalive': 0, 'endpoint': None, 'port': 0,
    'allowed-ips': [], 'pubkey': None, 'fwmark': 0, 'psk': '/dev/null'}
    >>> wg_intfc.wg_config['keepalive'] = 100
    >>> print (wg_intfc.wg_config)
    {'private-key': None, 'keepalive': 100, 'endpoint': None, 'port': 0,
    'allowed-ips': [], 'pubkey': None, 'fwmark': 0, 'psk': '/dev/null'}
    """

    def update(self):
        if not self.config['private-key']:
            raise ValueError("private key required")
        else:
            # fmask permission check?
            pass

        cmd = "wg set {} ".format(self.config['ifname'])
        cmd += "listen-port {} ".format(self.config['port'])
        cmd += "fwmark {} ".format(str(self.config['fwmark']))
        cmd += "private-key {} ".format(self.config['private-key'])
        cmd += "peer {} ".format(self.config['pubkey'])
        cmd += " preshared-key {} ".format(self.config['psk'])
        cmd += " allowed-ips "
        for aip in self.config['allowed-ips']:
            if aip != self.config['allowed-ips'][-1]:
                cmd += aip + ","
            else:
                cmd += aip
        if self.config['endpoint']:
            cmd += " endpoint {}".format(self.config['endpoint'])
        cmd += " persistent-keepalive {}".format(self.config['keepalive'])

        self._cmd(cmd)

        # remove psk since it isn't required anymore and is saved in the cli
        # config only !!
        if self.config['psk'] != '/dev/null':
            if os.path.exists(self.config['psk']):
                os.remove(self.config['psk'])

    def remove_peer(self, peerkey):
        """
        Remove a peer of an interface, peers are identified by their public key.
        Giving it a readable name is a vyos feature, to remove a peer the pubkey
        and the interface is needed, to remove the entry.
        """
        cmd = "wg set {0} peer {1} remove".format(
            self.config['ifname'], str(peerkey))
        return self._cmd(cmd)

    def op_show_interface(self):
        wgdump = vyos.interfaces.wireguard_dump().get(
            self.config['ifname'], None)

        c = vyos.config.Config()
        c.set_level(["interfaces", "wireguard", self.config['ifname']])
        description = c.return_effective_value(["description"])
        ips = c.return_effective_values(["address"])

        print ("interface: {}".format(self.config['ifname']))
        if (description):
            print ("  description: {}".format(description))

        if (ips):
            print ("  address: {}".format(", ".join(ips)))
        print ("  public key: {}".format(wgdump['public_key']))
        print ("  private key: (hidden)")
        print ("  listening port: {}".format(wgdump['listen_port']))
        print ()

        for peer in c.list_effective_nodes(["peer"]):
            if wgdump['peers']:
                pubkey = c.return_effective_value(["peer", peer, "pubkey"])
                if pubkey in wgdump['peers']:
                    wgpeer = wgdump['peers'][pubkey]

                    print ("  peer: {}".format(peer))
                    print ("    public key: {}".format(pubkey))

                    """ figure out if the tunnel is recently active or not """
                    status = "inactive"
                    if (wgpeer['latest_handshake'] is None):
                        """ no handshake ever """
                        status = "inactive"
                    else:
                        if int(wgpeer['latest_handshake']) > 0:
                            delta = timedelta(seconds=int(
                                time.time() - wgpeer['latest_handshake']))
                            print ("    latest handshake: {}".format(delta))
                            if (time.time() - int(wgpeer['latest_handshake']) < (60*5)):
                                """ Five minutes and the tunnel is still active """
                                status = "active"
                            else:
                                """ it's been longer than 5 minutes """
                                status = "inactive"
                        elif int(wgpeer['latest_handshake']) == 0:
                            """ no handshake ever """
                            status = "inactive"
                        print ("    status: {}".format(status))

                    if wgpeer['endpoint'] is not None:
                        print ("    endpoint: {}".format(wgpeer['endpoint']))

                    if wgpeer['allowed_ips'] is not None:
                        print ("    allowed ips: {}".format(
                            ",".join(wgpeer['allowed_ips']).replace(",", ", ")))

                    if wgpeer['transfer_rx'] > 0 or wgpeer['transfer_tx'] > 0:
                        rx_size = size(
                            wgpeer['transfer_rx'], system=alternative)
                        tx_size = size(
                            wgpeer['transfer_tx'], system=alternative)
                        print ("    transfer: {} received, {} sent".format(
                            rx_size, tx_size))

                    if wgpeer['persistent_keepalive'] is not None:
                        print ("    persistent keepalive: every {} seconds".format(
                            wgpeer['persistent_keepalive']))
                print()
        super().op_show_interface_stats()
