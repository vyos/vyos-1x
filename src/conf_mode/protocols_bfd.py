#!/usr/bin/env python3
#
# Copyright (C) 2019-2020 VyOS maintainers and contributors
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
from copy import deepcopy
from jinja2 import FileSystemLoader, Environment

from vyos.config import Config
from vyos.defaults import directories as vyos_data_dir
from vyos.validate import is_ipv6_link_local, is_ipv6
from vyos import ConfigError
from vyos.util import call


config_file = r'/tmp/bfd.frr'

default_config_data = {
    'new_peers': [],
    'old_peers' : []
}

# get configuration for BFD peer from proposed or effective configuration
def get_bfd_peer_config(peer, conf_mode="proposed"):
    conf = Config()
    conf.set_level('protocols bfd peer {0}'.format(peer))

    bfd_peer = {
        'remote': peer,
        'shutdown': False,
        'src_if': '',
        'src_addr': '',
        'multiplier': '3',
        'rx_interval': '300',
        'tx_interval': '300',
        'multihop': False,
        'echo_interval': '',
        'echo_mode': False,
    }

    # Check if individual peer is disabled
    if conf_mode == "effective" and conf.exists_effective('shutdown'):
        bfd_peer['shutdown'] = True
    if conf_mode == "proposed" and conf.exists('shutdown'):
        bfd_peer['shutdown'] = True

    # Check if peer has a local source interface configured
    if conf_mode == "effective" and conf.exists_effective('source interface'):
        bfd_peer['src_if'] = conf.return_effective_value('source interface')
    if conf_mode == "proposed" and conf.exists('source interface'):
        bfd_peer['src_if'] = conf.return_value('source interface')

    # Check if peer has a local source address configured - this is mandatory for IPv6
    if conf_mode == "effective" and conf.exists_effective('source address'):
        bfd_peer['src_addr'] = conf.return_effective_value('source address')
    if conf_mode == "proposed" and conf.exists('source address'):
        bfd_peer['src_addr'] = conf.return_value('source address')

    # Tell BFD daemon that we should expect packets with TTL less than 254
    # (because it will take more than one hop) and to listen on the multihop
    # port (4784)
    if conf_mode == "effective" and conf.exists_effective('multihop'):
        bfd_peer['multihop'] = True
    if conf_mode == "proposed" and conf.exists('multihop'):
        bfd_peer['multihop'] = True

    # Configures the minimum interval that this system is capable of receiving
    # control packets. The default value is 300 milliseconds.
    if conf_mode == "effective" and conf.exists_effective('interval receive'):
        bfd_peer['rx_interval'] = conf.return_effective_value('interval receive')
    if conf_mode == "proposed" and conf.exists('interval receive'):
        bfd_peer['rx_interval'] = conf.return_value('interval receive')

    # The minimum transmission interval (less jitter) that this system wants
    # to use to send BFD control packets.
    if conf_mode == "effective" and conf.exists_effective('interval transmit'):
        bfd_peer['tx_interval'] = conf.return_effective_value('interval transmit')
    if conf_mode == "proposed" and conf.exists('interval transmit'):
        bfd_peer['tx_interval'] = conf.return_value('interval transmit')

    # Configures the detection multiplier to determine packet loss. The remote
    # transmission interval will be multiplied by this value to determine the
    # connection loss detection timer. The default value is 3.
    if conf_mode == "effective" and conf.exists_effective('interval multiplier'):
        bfd_peer['multiplier'] = conf.return_effective_value('interval multiplier')
    if conf_mode == "proposed" and conf.exists('interval multiplier'):
        bfd_peer['multiplier'] = conf.return_value('interval multiplier')

    # Configures the minimal echo receive transmission interval that this system is capable of handling
    if conf_mode == "effective" and conf.exists_effective('interval echo-interval'):
        bfd_peer['echo_interval'] = conf.return_effective_value('interval echo-interval')
    if conf_mode == "proposed" and conf.exists('interval echo-interval'):
        bfd_peer['echo_interval'] = conf.return_value('interval echo-interval')

    # Enables or disables the echo transmission mode
    if conf_mode == "effective" and conf.exists_effective('echo-mode'):
        bfd_peer['echo_mode'] = True
    if conf_mode == "proposed" and conf.exists('echo-mode'):
        bfd_peer['echo_mode'] = True

    return bfd_peer

def get_config():
    bfd = deepcopy(default_config_data)
    conf = Config()
    if not (conf.exists('protocols bfd') or conf.exists_effective('protocols bfd')):
        return None
    else:
        conf.set_level('protocols bfd')

    # as we have to use vtysh to talk to FRR we also need to know
    # which peers are gone due to a config removal - thus we read in
    # all peers (active or to delete)
    for peer in conf.list_effective_nodes('peer'):
        bfd['old_peers'].append(get_bfd_peer_config(peer, "effective"))

    for peer in conf.list_nodes('peer'):
        bfd['new_peers'].append(get_bfd_peer_config(peer))

    # find deleted peers
    set_new_peers = set(conf.list_nodes('peer'))
    set_old_peers = set(conf.list_effective_nodes('peer'))
    bfd['deleted_peers'] = set_old_peers - set_new_peers

    return bfd

def verify(bfd):
    if bfd is None:
        return None

    # some variables to use later
    conf = Config()

    for peer in bfd['new_peers']:
        # IPv6 link local peers require an explicit local address/interface
        if is_ipv6_link_local(peer['remote']):
            if not (peer['src_if'] and peer['src_addr']):
                raise ConfigError('BFD IPv6 link-local peers require explicit local address and interface setting')

        # IPv6 peers require an explicit local address
        if is_ipv6(peer['remote']):
            if not peer['src_addr']:
                raise ConfigError('BFD IPv6 peers require explicit local address setting')

        # multihop require source address
        if peer['multihop'] and not peer['src_addr']:
            raise ConfigError('Multihop require source address')

        # multihop and echo-mode cannot be used together
        if peer['multihop'] and peer['echo_mode']:
            raise ConfigError('Multihop and echo-mode cannot be used together')

        # multihop doesn't accept interface names
        if peer['multihop'] and peer['src_if']:
            raise ConfigError('Multihop and source interface cannot be used together')

        # echo interval can be configured only with enabled echo-mode
        if peer['echo_interval'] != '' and not peer['echo_mode']:
            raise ConfigError('echo-interval can be configured only with enabled echo-mode')

    # check if we deleted peers are not used in configuration
    if conf.exists('protocols bgp'):
        bgp_as = conf.list_nodes('protocols bgp')[0]

        # check BGP neighbors
        for peer in bfd['deleted_peers']:
            if conf.exists('protocols bgp {0} neighbor {1} bfd'.format(bgp_as, peer)):
                raise ConfigError('Cannot delete BFD peer {0}: it is used in BGP configuration'.format(peer))
            if conf.exists('protocols bgp {0} neighbor {1} peer-group'.format(bgp_as, peer)):
                peer_group = conf.return_value('protocols bgp {0} neighbor {1} peer-group'.format(bgp_as, peer))
                if conf.exists('protocols bgp {0} peer-group {1} bfd'.format(bgp_as, peer_group)):
                    raise ConfigError('Cannot delete BFD peer {0}: it belongs to BGP peer-group {1} with enabled BFD'.format(peer, peer_group))

    return None

def generate(bfd):
    if bfd is None:
        return None

    # Prepare Jinja2 template loader from files
    tmpl_path = os.path.join(vyos_data_dir['data'], 'templates', 'frr-bfd')
    fs_loader = FileSystemLoader(tmpl_path)
    env = Environment(loader=fs_loader)

    tmpl = env.get_template('bfd.frr.tmpl')
    config_text = tmpl.render(bfd)
    with open(config_file, 'w') as f:
        f.write(config_text)

    return None

def apply(bfd):
    if bfd is None:
        return None

    call("vtysh -d bfdd -f " + config_file)
    if os.path.exists(config_file):
        os.remove(config_file)

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
