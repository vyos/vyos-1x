# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

from hashlib import sha256
from ipaddress import ip_address, ip_interface, ip_network

from vyos import ConfigError
from vyos.config import Config
from vyos.ifconfig import Interface
from vyos.utils.dict import dict_search
from vyos.utils.network import interface_exists

def verify_native_bridge(network: dict, bridge: dict) -> None:
    ifname = dict_search('type.bridge.interface', network)
    if not bridge or 'deleted' in bridge or 'disable' in bridge:
        raise ConfigError(f'VyOS bridge "{ifname}" must be configured and enabled!')
    if 'vrf' in bridge:
        raise ConfigError('Unmanaged container bridges do not support VRFs yet!')
    mtu = int(network.get('mtu', '1500'))
    if mtu != int(bridge.get('mtu', '1500')):
        raise ConfigError(f'Container network MTU must match bridge "{ifname}"!')
    addresses = [ip_interface(a) for a in bridge.get('address', [])
                 if a not in ['dhcp', 'dhcpv6']]
    for prefix in network.get('prefix', []):
        subnet = ip_network(prefix)
        if subnet.version == 6 and mtu < 1280:
            raise ConfigError('IPv6 container networks require an MTU of at least 1280!')
        gateway = next((ip_address(g) for g in network.get('gateway', [])
                        if ip_address(g).version == subnet.version),
                       subnet.network_address + 1)
        if not any(a.ip == gateway and a.network == subnet for a in addresses):
            raise ConfigError(f'Gateway "{gateway}/{subnet.prefixlen}" must be '
                              f'assigned to bridge "{ifname}"!')

def get_container_host_ifname(name: str) -> str:
    """
    Deterministic host-side veth interface name for a container's network
    attachment (verify() only allows one network per container). Kept within
    IFNAMSIZ and - thanks to the leading "veth-" (a hyphen can never appear in
    a VyOS "vethN" interface name) - guaranteed to never collide with the
    "virtual-ethernet" naming scheme..
    """
    prefix = f'veth-{name}'
    if len(prefix) <= 15:
        return prefix
    digest = sha256(name.encode()).hexdigest()[:4]
    return f'veth-{name[:5]}-{digest}'

def restart_network(config: Config) -> None:
    """
    Start network and assign it to given VRF if requested.

    This can only be done after the containers got started as the podman network
    interface will only be enabled by the first container and yet I do not know
    how to enable the network interface in advance.
    """
    if 'network' in config:
        for network, network_config in config['network'].items():
            if dict_search('type.bridge.interface', network_config) is not None:
                continue
            type_config = dict_search('type', network_config)
            if not dict_search('macvlan', type_config):
                network_name = f'pod-{network}'
                # T5147: Networks are started only as soon as there is a consumer.
                # If only a network is created in the first place, no need to assign
                # it to a VRF as there's no consumer, yet.
                if interface_exists(network_name):
                    tmp = Interface(network_name)
                    tmp.set_vrf(network_config.get('vrf', ''))
                    tmp.add_ipv6_eui64_address('fe80::/64')

    return None
