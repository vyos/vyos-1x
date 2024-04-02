# Copyright 2019-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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
from tempfile import NamedTemporaryFile

from hurry.filesize import size
from hurry.filesize import alternative

from vyos.ifconfig import Interface
from vyos.ifconfig import Operational
from vyos.template import is_ipv6

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
        from vyos.config import Config
        c = Config()

        wgdump = self._dump().get(self.config['ifname'], None)

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
                pubkey = c.return_effective_value(["peer", peer, "public_key"])
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
    iftype = 'wireguard'
    definition = {
        **Interface.definition,
        **{
            'section': 'wireguard',
            'prefixes': ['wg', ],
            'bridgeable': False,
        }
    }

    def get_mac(self):
        """ Get a synthetic MAC address. """
        return self.get_mac_synthetic()

    def update(self, config):
        """ General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface. """

        tmp_file = NamedTemporaryFile('w')
        tmp_file.write(config['private_key'])
        tmp_file.flush()

        # Wireguard base command is identical for every peer
        base_cmd  = 'wg set {ifname}'
        if 'port' in config:
            base_cmd += ' listen-port {port}'
        if 'fwmark' in config:
            base_cmd += ' fwmark {fwmark}'

        base_cmd += f' private-key {tmp_file.name}'
        base_cmd = base_cmd.format(**config)
        if 'peer' in config:
            for peer, peer_config in config['peer'].items():
                # T4702: No need to configure this peer when it was explicitly
                # marked as disabled - also active sessions are terminated as
                # the public key was already removed when entering this method!
                if 'disable' in peer_config:
                    continue

                # start of with a fresh 'wg' command
                cmd = base_cmd + ' peer {public_key}'

                # If no PSK is given remove it by using /dev/null - passing keys via
                # the shell (usually bash) is considered insecure, thus we use a file
                no_psk_file = '/dev/null'
                psk_file = no_psk_file
                if 'preshared_key' in peer_config:
                    psk_file = '/tmp/tmp.wireguard.psk'
                    with open(psk_file, 'w') as f:
                        f.write(peer_config['preshared_key'])
                cmd += f' preshared-key {psk_file}'

                # Persistent keepalive is optional
                if 'persistent_keepalive'in peer_config:
                    cmd += ' persistent-keepalive {persistent_keepalive}'

                # Multiple allowed-ip ranges can be defined - ensure we are always
                # dealing with a list
                if isinstance(peer_config['allowed_ips'], str):
                    peer_config['allowed_ips'] = [peer_config['allowed_ips']]
                cmd += ' allowed-ips ' + ','.join(peer_config['allowed_ips'])

                # Endpoint configuration is optional
                if {'address', 'port'} <= set(peer_config):
                    if is_ipv6(peer_config['address']):
                        cmd += ' endpoint [{address}]:{port}'
                    else:
                        cmd += ' endpoint {address}:{port}'

                self._cmd(cmd.format(**peer_config))

                # PSK key file is not required to be stored persistently as its backed by CLI
                if psk_file != no_psk_file and os.path.exists(psk_file):
                    os.remove(psk_file)

        # call base class
        super().update(config)
