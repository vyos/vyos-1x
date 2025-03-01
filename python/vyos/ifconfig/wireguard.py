# Copyright 2019-2025 VyOS maintainers and contributors <maintainers@vyos.io>
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

from tempfile import NamedTemporaryFile

from vyos.configquery import ConfigTreeQuery
from vyos.ifconfig import Interface
from vyos.ifconfig import Operational
from vyos.template import is_ipv6
from vyos.template import is_ipv4

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
                (
                    device,
                    public_key,
                    preshared_key,
                    endpoint,
                    allowed_ips,
                    latest_handshake,
                    transfer_rx,
                    transfer_tx,
                    persistent_keepalive,
                ) = items
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

        c.set_level(['interfaces', 'wireguard', self.config['ifname']])
        description = c.return_effective_value(['description'])
        ips = c.return_effective_values(['address'])
        hostnames = c.return_effective_values(['host-name'])

        answer = 'interface: {}\n'.format(self.config['ifname'])
        if description:
            answer += '  description: {}\n'.format(description)
        if ips:
            answer += '  address: {}\n'.format(', '.join(ips))
        if hostnames:
            answer += '  hostname: {}\n'.format(', '.join(hostnames))

        answer += '  public key: {}\n'.format(wgdump['public_key'])
        answer += '  private key: (hidden)\n'
        answer += '  listening port: {}\n'.format(wgdump['listen_port'])
        answer += '\n'

        for peer in c.list_effective_nodes(['peer']):
            if wgdump['peers']:
                pubkey = c.return_effective_value(['peer', peer, 'public-key'])
                if pubkey in wgdump['peers']:
                    wgpeer = wgdump['peers'][pubkey]

                    answer += '  peer: {}\n'.format(peer)
                    answer += '    public key: {}\n'.format(pubkey)

                    """ figure out if the tunnel is recently active or not """
                    status = 'inactive'
                    if wgpeer['latest_handshake'] is None:
                        """ no handshake ever """
                        status = 'inactive'
                    else:
                        if int(wgpeer['latest_handshake']) > 0:
                            delta = timedelta(
                                seconds=int(time.time() - wgpeer['latest_handshake'])
                            )
                            answer += '    latest handshake: {}\n'.format(delta)
                            if time.time() - int(wgpeer['latest_handshake']) < (60 * 5):
                                """ Five minutes and the tunnel is still active """
                                status = 'active'
                            else:
                                """ it's been longer than 5 minutes """
                                status = 'inactive'
                        elif int(wgpeer['latest_handshake']) == 0:
                            """ no handshake ever """
                            status = 'inactive'
                        answer += '    status: {}\n'.format(status)

                    if wgpeer['endpoint'] is not None:
                        answer += '    endpoint: {}\n'.format(wgpeer['endpoint'])

                    if wgpeer['allowed_ips'] is not None:
                        answer += '    allowed ips: {}\n'.format(
                            ','.join(wgpeer['allowed_ips']).replace(',', ', ')
                        )

                    if wgpeer['transfer_rx'] > 0 or wgpeer['transfer_tx'] > 0:
                        rx_size = size(wgpeer['transfer_rx'], system=alternative)
                        tx_size = size(wgpeer['transfer_tx'], system=alternative)
                        answer += '    transfer: {} received, {} sent\n'.format(
                            rx_size, tx_size
                        )

                    if wgpeer['persistent_keepalive'] is not None:
                        answer += '    persistent keepalive: every {} seconds\n'.format(
                            wgpeer['persistent_keepalive']
                        )
                answer += '\n'
        return answer

    def get_latest_handshakes(self):
        """Get latest handshake time for each peer"""
        output = {}

        # Dump wireguard last handshake
        tmp = self._cmd(f'wg show {self.ifname} latest-handshakes')
        # Output:
        # PUBLIC-KEY=    1732812147
        for line in tmp.split('\n'):
            if not line:
                # Skip empty lines and last line
                continue
            items = line.split('\t')

            if len(items) != 2:
                continue

            output[items[0]] = int(items[1])

        return output

    def reset_peer(self, peer_name=None, public_key=None):
        c = ConfigTreeQuery()
        tmp = c.get_config_dict(['interfaces', 'wireguard', self.ifname],
                                effective=True, get_first_key=True,
                                key_mangling=('-', '_'), with_defaults=True)

        current_peers = self._dump().get(self.ifname, {}).get('peers', {})

        for peer, peer_config in tmp['peer'].items():
            peer_public_key = peer_config['public_key']
            if peer_name is None or peer == peer_name or public_key == peer_public_key:
                if ('address' not in peer_config and 'host_name' not in peer_config) or 'port' not in peer_config:
                    if peer_name is not None:
                        print(f'WireGuard interface "{self.ifname}" peer "{peer_name}" address/host-name unset!')
                    continue

                # As we work with an effective config, a port CLI node is always
                # available when an address/host-name is defined on the CLI
                port = peer_config['port']

                # address has higher priority than host-name
                if 'address' in peer_config:
                    address = peer_config['address']
                    new_endpoint = f'{address}:{port}'
                else:
                    host_name = peer_config['host_name']
                    new_endpoint = f'{host_name}:{port}'

                if 'disable' in peer_config:
                    print(f'WireGuard interface "{self.ifname}" peer "{peer_name}" disabled!')
                    continue

                cmd = f'wg set {self.ifname} peer {peer_public_key} endpoint {new_endpoint}'
                try:
                    if (peer_public_key in current_peers
                        and 'endpoint' in current_peers[peer_public_key]
                        and current_peers[peer_public_key]['endpoint'] is not None
                    ):
                        current_endpoint = current_peers[peer_public_key]['endpoint']
                        message = f'Resetting {self.ifname} peer {peer_public_key} from {current_endpoint} endpoint to {new_endpoint} ... '
                    else:
                        message = f'Resetting {self.ifname} peer {peer_public_key} endpoint to {new_endpoint} ... '
                    print(message, end='')

                    self._cmd(cmd, env={'WG_ENDPOINT_RESOLUTION_RETRIES':
                                        tmp['max_dns_retry']})
                    print('done')
                except:
                    print(f'Error\nPlease try to run command manually:\n{cmd}\n')


@Interface.register
class WireGuardIf(Interface):
    OperationalClass = WireGuardOperational
    definition = {
        **Interface.definition,
        **{
            'section': 'wireguard',
            'prefixes': ['wg', ],
            'bridgeable': False,
        },
    }

    def _create(self):
        super()._create('wireguard')

    def get_mac(self):
        """Get a synthetic MAC address."""
        return self.get_mac_synthetic()

    def update(self, config):
        """General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface."""
        tmp_file = NamedTemporaryFile('w')
        tmp_file.write(config['private_key'])
        tmp_file.flush()

        # Wireguard base command is identical for every peer
        base_cmd = f'wg set {self.ifname}'
        interface_cmd = base_cmd
        if 'port' in config:
            interface_cmd += ' listen-port {port}'
        if 'fwmark' in config:
            interface_cmd += ' fwmark {fwmark}'

        interface_cmd += f' private-key {tmp_file.name}'
        interface_cmd = interface_cmd.format(**config)
        # T6490: execute command to ensure interface configured
        self._cmd(interface_cmd)

        # If no PSK is given remove it by using /dev/null - passing keys via
        # the shell (usually bash) is considered insecure, thus we use a file
        no_psk_file = '/dev/null'

        if 'peer' in config:
            for peer, peer_config in config['peer'].items():
                # T4702: No need to configure this peer when it was explicitly
                # marked as disabled - also active sessions are terminated as
                # the public key was already removed when entering this method!
                if 'disable' in peer_config:
                    # remove peer if disabled, no error report even if peer not exists
                    cmd = base_cmd + ' peer {public_key} remove'
                    self._cmd(cmd.format(**peer_config))
                    continue

                psk_file = no_psk_file

                # start of with a fresh 'wg' command
                peer_cmd = base_cmd + ' peer {public_key}'

                try:
                    cmd = peer_cmd

                    if 'preshared_key' in peer_config:
                        psk_file = '/tmp/tmp.wireguard.psk'
                        with open(psk_file, 'w') as f:
                            f.write(peer_config['preshared_key'])
                    cmd += f' preshared-key {psk_file}'

                    # Persistent keepalive is optional
                    if 'persistent_keepalive' in peer_config:
                        cmd += ' persistent-keepalive {persistent_keepalive}'

                    # Multiple allowed-ip ranges can be defined - ensure we are always
                    # dealing with a list
                    if isinstance(peer_config['allowed_ips'], str):
                        peer_config['allowed_ips'] = [peer_config['allowed_ips']]
                    cmd += ' allowed-ips ' + ','.join(peer_config['allowed_ips'])

                    self._cmd(cmd.format(**peer_config))

                    cmd = peer_cmd

                    # Ensure peer is created even if dns not working
                    if {'address', 'port'} <= set(peer_config):
                        if is_ipv6(peer_config['address']):
                            cmd += ' endpoint [{address}]:{port}'
                        elif is_ipv4(peer_config['address']):
                            cmd += ' endpoint {address}:{port}'
                        else:
                            # don't set endpoint if address uses domain name
                            continue
                    elif {'host_name', 'port'} <= set(peer_config):
                        cmd += ' endpoint {host_name}:{port}'

                    self._cmd(cmd.format(**peer_config), env={
                        'WG_ENDPOINT_RESOLUTION_RETRIES': config['max_dns_retry']})
                except:
                    # todo: logging
                    pass
                finally:
                    # PSK key file is not required to be stored persistently as its backed by CLI
                    if psk_file != no_psk_file and os.path.exists(psk_file):
                        os.remove(psk_file)

        # call base class
        super().update(config)
