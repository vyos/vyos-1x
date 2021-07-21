# Copyright 2019-2021 VyOS maintainers and contributors <maintainers@vyos.io>
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
from netaddr import EUI
from netaddr import mac_unix_expanded
from random import getrandbits

from hurry.filesize import size
from hurry.filesize import alternative

from vyos.config import Config
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
        """
        Get current interface MAC (Media Access Contrl) address used.

        NOTE: Tunnel interfaces have no "MAC" address by default. The content
              of the 'address' file in /sys/class/net/device contains the
              local-ip thus we generate a random MAC address instead

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').get_mac()
        '00:50:ab:cd:ef:00'
        """
        # we choose 40 random bytes for the MAC address, this gives
        # us e.g. EUI('00-EA-EE-D6-A3-C8') or EUI('00-41-B9-0D-F2-2A')
        tmp = EUI(getrandbits(48)).value
        # set locally administered bit in MAC address
        tmp |= 0xf20000000000
        # convert integer to "real" MAC address representation
        mac = EUI(hex(tmp).split('x')[-1])
        # change dialect to use : as delimiter instead of -
        mac.dialect = mac_unix_expanded
        return str(mac)

    def update(self, config):
        """ General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface. """

        # remove no longer associated peers first
        if 'peer_remove' in config:
            for tmp in config['peer_remove']:
                peer = config['peer_remove'][tmp]
                peer['ifname'] = config['ifname']

                cmd = 'wg set {ifname} peer {public_key} remove'
                self._cmd(cmd.format(**peer))

        config['private_key_file'] = '/tmp/tmp.wireguard.key'
        with open(config['private_key_file'], 'w') as f:
            f.write(config['private_key'])

        # Wireguard base command is identical for every peer
        base_cmd  = 'wg set {ifname} private-key {private_key_file}'
        if 'port' in config:
            base_cmd += ' listen-port {port}'
        if 'fwmark' in config:
            base_cmd += ' fwmark {fwmark}'

        base_cmd = base_cmd.format(**config)

        for tmp in config['peer']:
            peer = config['peer'][tmp]

            # start of with a fresh 'wg' command
            cmd = base_cmd + ' peer {public_key}'

            # If no PSK is given remove it by using /dev/null - passing keys via
            # the shell (usually bash) is considered insecure, thus we use a file
            no_psk_file = '/dev/null'
            psk_file = no_psk_file
            if 'preshared_key' in peer:
                psk_file = '/tmp/tmp.wireguard.psk'
                with open(psk_file, 'w') as f:
                    f.write(peer['preshared_key'])
            cmd += f' preshared-key {psk_file}'

            # Persistent keepalive is optional
            if 'persistent_keepalive'in peer:
                cmd += ' persistent-keepalive {persistent_keepalive}'

            # Multiple allowed-ip ranges can be defined - ensure we are always
            # dealing with a list
            if isinstance(peer['allowed_ips'], str):
                peer['allowed_ips'] = [peer['allowed_ips']]
            cmd += ' allowed-ips ' + ','.join(peer['allowed_ips'])

            # Endpoint configuration is optional
            if {'address', 'port'} <= set(peer):
                if is_ipv6(peer['address']):
                    cmd += ' endpoint [{address}]:{port}'
                else:
                    cmd += ' endpoint {address}:{port}'

            self._cmd(cmd.format(**peer))

            # PSK key file is not required to be stored persistently as its backed by CLI
            if psk_file != no_psk_file and os.path.exists(psk_file):
                os.remove(psk_file)

        # call base class
        super().update(config)
