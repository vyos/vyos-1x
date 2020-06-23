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
import time
from datetime import timedelta

from hurry.filesize import size
from hurry.filesize import alternative

from vyos.config import Config
from vyos.ifconfig import Interface
from vyos.ifconfig import Operational


class WireGuardOperational(Operational):
    def _dump(self):
        """Dump wireguard data in a python friendly way."""
        last_device = None
        output = {}

        # Dump wireguard connection data
        _f = self._cmd('wg show all dump')
        for line in _f.split('\n'):
            if not line:
                # Skip empty lines and last line
                continue
            items = line.split('\t')

            if last_device != items[0]:
                # We are currently entering a new node
                device, private_key, public_key, listen_port, fw_mark = items
                last_device = device

                output[device] = {
                    'private_key': None if private_key == '(none)' else private_key,
                    'public_key': None if public_key == '(none)' else public_key,
                    'listen_port': int(listen_port),
                    'fw_mark': None if fw_mark == 'off' else int(fw_mark),
                    'peers': {},
                }
            else:
                # We are entering a peer
                device, public_key, preshared_key, endpoint, allowed_ips, latest_handshake, transfer_rx, transfer_tx, persistent_keepalive = items
                if allowed_ips == '(none)':
                    allowed_ips = []
                else:
                    allowed_ips = allowed_ips.split('\t')
                output[device]['peers'][public_key] = {
                    'preshared_key': None if preshared_key == '(none)' else preshared_key,
                    'endpoint': None if endpoint == '(none)' else endpoint,
                    'allowed_ips': allowed_ips,
                    'latest_handshake': None if latest_handshake == '0' else int(latest_handshake),
                    'transfer_rx': int(transfer_rx),
                    'transfer_tx': int(transfer_tx),
                    'persistent_keepalive': None if persistent_keepalive == 'off' else int(persistent_keepalive),
                }
        return output

    def show_interface(self):
        wgdump = self._dump().get(self.config['ifname'], None)

        c = Config()

        c.set_level(["interfaces", "wireguard", self.config['ifname']])
        description = c.return_effective_value(["description"])
        ips = c.return_effective_values(["address"])

        answer = "interface: {}\n".format(self.config['ifname'])
        if (description):
            answer += "  description: {}\n".format(description)
        if (ips):
            answer += "  address: {}\n".format(", ".join(ips))

        answer += "  public key: {}\n".format(wgdump['public_key'])
        answer += "  private key: (hidden)\n"
        answer += "  listening port: {}\n".format(wgdump['listen_port'])
        answer += "\n"

        for peer in c.list_effective_nodes(["peer"]):
            if wgdump['peers']:
                pubkey = c.return_effective_value(["peer", peer, "pubkey"])
                if pubkey in wgdump['peers']:
                    wgpeer = wgdump['peers'][pubkey]

                    answer += "  peer: {}\n".format(peer)
                    answer += "    public key: {}\n".format(pubkey)

                    """ figure out if the tunnel is recently active or not """
                    status = "inactive"
                    if (wgpeer['latest_handshake'] is None):
                        """ no handshake ever """
                        status = "inactive"
                    else:
                        if int(wgpeer['latest_handshake']) > 0:
                            delta = timedelta(seconds=int(
                                time.time() - wgpeer['latest_handshake']))
                            answer += "    latest handshake: {}\n".format(delta)
                            if (time.time() - int(wgpeer['latest_handshake']) < (60*5)):
                                """ Five minutes and the tunnel is still active """
                                status = "active"
                            else:
                                """ it's been longer than 5 minutes """
                                status = "inactive"
                        elif int(wgpeer['latest_handshake']) == 0:
                            """ no handshake ever """
                            status = "inactive"
                        answer += "    status: {}\n".format(status)

                    if wgpeer['endpoint'] is not None:
                        answer += "    endpoint: {}\n".format(wgpeer['endpoint'])

                    if wgpeer['allowed_ips'] is not None:
                        answer += "    allowed ips: {}\n".format(
                            ",".join(wgpeer['allowed_ips']).replace(",", ", "))

                    if wgpeer['transfer_rx'] > 0 or wgpeer['transfer_tx'] > 0:
                        rx_size = size(
                            wgpeer['transfer_rx'], system=alternative)
                        tx_size = size(
                            wgpeer['transfer_tx'], system=alternative)
                        answer += "    transfer: {} received, {} sent\n".format(
                            rx_size, tx_size)

                    if wgpeer['persistent_keepalive'] is not None:
                        answer += "    persistent keepalive: every {} seconds\n".format(
                            wgpeer['persistent_keepalive'])
                answer += '\n'
        return answer + super().formated_stats()


@Interface.register
class WireGuardIf(Interface):
    OperationalClass = WireGuardOperational

    default = {
        'type': 'wireguard',
        'port': 0,
        'private_key': None,
        'pubkey': None,
        'psk': '',
        'allowed_ips': [],
        'fwmark': 0x00,
        'endpoint': None,
        'keepalive': 0
    }
    definition = {
        **Interface.definition,
        **{
            'section': 'wireguard',
            'prefixes': ['wg', ],
            'bridgeable': True,
        }
    }
    options = Interface.options + \
        ['port', 'private_key', 'pubkey', 'psk',
         'allowed_ips', 'fwmark', 'endpoint', 'keepalive']

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
    {'private_key': None, 'keepalive': 0, 'endpoint': None, 'port': 0,
    'allowed_ips': [], 'pubkey': None, 'fwmark': 0, 'psk': '/dev/null'}
    >>> wg_intfc.wg_config['keepalive'] = 100
    >>> print (wg_intfc.wg_config)
    {'private_key': None, 'keepalive': 100, 'endpoint': None, 'port': 0,
    'allowed_ips': [], 'pubkey': None, 'fwmark': 0, 'psk': '/dev/null'}
    """

    def update(self):
        if not self.config['private_key']:
            raise ValueError("private key required")
        else:
            # fmask permission check?
            pass

        cmd  = 'wg set {ifname}'.format(**self.config)
        cmd += ' listen-port {port}'.format(**self.config)
        cmd += ' fwmark "{fwmark}" '.format(**self.config)
        cmd += ' private-key {private_key}'.format(**self.config)
        cmd += ' peer {pubkey}'.format(**self.config)
        cmd += ' persistent-keepalive {keepalive}'.format(**self.config)
        cmd += ' allowed-ips {}'.format(', '.join(self.config['allowed-ips']))

        if self.config['endpoint']:
            cmd += ' endpoint "{endpoint}"'.format(**self.config)

        psk_file = ''
        if self.config['psk']:
            psk_file = '/tmp/{ifname}.psk'.format(**self.config)
            with open(psk_file, 'w') as f:
                f.write(self.config['psk'])
            cmd += f' preshared-key {psk_file}'

        self._cmd(cmd)

        # PSK key file is not required to be stored persistently as its backed by CLI
        if os.path.exists(psk_file):
            os.remove(psk_file)

    def remove_peer(self, peerkey):
        """
        Remove a peer of an interface, peers are identified by their public key.
        Giving it a readable name is a vyos feature, to remove a peer the pubkey
        and the interface is needed, to remove the entry.
        """
        cmd = "wg set {0} peer {1} remove".format(
            self.config['ifname'], str(peerkey))
        return self._cmd(cmd)
