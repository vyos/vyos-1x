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

from vyos.config import Config
from vyos.ifconfig import Interface
from vyos.utils.dict import dict_search
from vyos.utils.network import interface_exists

def restart_network(config: Config) -> None:
    """
    Start network and assign it to given VRF if requested.

    This can only be done after the containers got started as the podman network
    interface will only be enabled by the first container and yet I do not know
    how to enable the network interface in advance.
    """
    if 'network' in config:
        for network, network_config in config['network'].items():
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
