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

# https://developers.redhat.com/blog/2019/05/17/an-introduction-to-linux-virtual-interfaces-tunnels/
# https://community.hetzner.com/tutorials/linux-setup-gre-tunnel

from vyos.ifconfig.interface import Interface
from vyos.utils.dict import dict_search
from vyos.utils.assertion import assert_list

def enable_to_on(value):
    if value == 'enable':
        return 'on'
    if value == 'disable':
        return 'off'
    raise ValueError(f'expect enable or disable but got "{value}"')

@Interface.register
class TunnelIf(Interface):
    """
    Tunnel: private base class for tunnels
    https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/ip/tunnel.c
    https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/ip/ip6tunnel.c
    """
    definition = {
        **Interface.definition,
        **{
            'section': 'tunnel',
            'prefixes': ['tun',],
            'bridgeable': True,
        },
    }

    # This table represents a mapping from VyOS internal config dict to
    # arguments used by iproute2. For more information please refer to:
    # - https://man7.org/linux/man-pages/man8/ip-link.8.html
    # - https://man7.org/linux/man-pages/man8/ip-tunnel.8.html
    mapping = {
        'source_address'                  : 'local',
        'source_interface'                : 'dev',
        'remote'                          : 'remote',
        'parameters.ip.key'               : 'key',
        'parameters.ip.tos'               : 'tos',
        'parameters.ip.ttl'               : 'ttl',
    }
    mapping_ipv4 = {
        'parameters.ip.key'               : 'key',
        'parameters.ip.no_pmtu_discovery' : 'nopmtudisc',
        'parameters.ip.ignore_df'         : 'ignore-df',
        'parameters.ip.tos'               : 'tos',
        'parameters.ip.ttl'               : 'ttl',
        'parameters.erspan.direction'     : 'erspan_dir',
        'parameters.erspan.hw_id'         : 'erspan_hwid',
        'parameters.erspan.index'         : 'erspan',
        'parameters.erspan.version'       : 'erspan_ver',
    }
    mapping_ipv6 = {
        'parameters.ipv6.encaplimit'      : 'encaplimit',
        'parameters.ipv6.flowlabel'       : 'flowlabel',
        'parameters.ipv6.hoplimit'        : 'hoplimit',
        'parameters.ipv6.tclass'          : 'tclass',
    }

    # TODO: This is surely used for more than tunnels
    # TODO: could be refactored elsewhere
    _command_set = {
        **Interface._command_set,
        **{
            'multicast': {
                'validate': lambda v: assert_list(v, ['enable', 'disable']),
                'convert': enable_to_on,
                'shellcmd': 'ip link set dev {ifname} multicast {value}',
            },
        }
    }

    def __init__(self, ifname, **kargs):
        # T3357: we do not have the 'encapsulation' in kargs when calling this
        # class from op-mode like "show interfaces tunnel"
        if 'encapsulation' in kargs:
            self.iftype = kargs['encapsulation']
            # The gretap interface has the possibility to act as L2 bridge
            if self.iftype in ['gretap', 'ip6gretap']:
                # no multicast, ttl or tos for gretap
                self.definition = {
                    **TunnelIf.definition,
                    **{
                        'bridgeable': True,
                    },
                }

        super().__init__(ifname, **kargs)

    def _create(self):
        if self.config['encapsulation'] in ['ipip6', 'ip6ip6', 'ip6gre']:
            mapping = { **self.mapping, **self.mapping_ipv6 }
        else:
            mapping = { **self.mapping, **self.mapping_ipv4 }

        cmd = 'ip tunnel add {ifname} mode {encapsulation}'
        if self.iftype in ['gretap', 'ip6gretap', 'erspan', 'ip6erspan']:
            cmd = 'ip link add name {ifname} type {encapsulation}'
            # ERSPAN requires the serialisation of packets
            if self.iftype in ['erspan', 'ip6erspan']:
                cmd += ' seq'

        for vyos_key, iproute2_key in mapping.items():
            # dict_search will return an empty dict "{}" for valueless nodes like
            # "parameters.nolearning" - thus we need to test the nodes existence
            # by using isinstance()
            tmp = dict_search(vyos_key, self.config)
            if isinstance(tmp, dict):
                cmd += f' {iproute2_key}'
            elif tmp != None:
                cmd += f' {iproute2_key} {tmp}'

        self._cmd(cmd.format(**self.config))

        self.set_admin_state('down')

    def _change_options(self):
        # gretap interfaces do not support changing any parameter
        if self.iftype in ['gretap', 'ip6gretap', 'erspan', 'ip6erspan']:
            return

        if self.config['encapsulation'] in ['ipip6', 'ip6ip6', 'ip6gre']:
            mapping = { **self.mapping, **self.mapping_ipv6 }
        else:
            mapping = { **self.mapping, **self.mapping_ipv4 }

        cmd = 'ip tunnel change {ifname} mode {encapsulation}'
        for vyos_key, iproute2_key in mapping.items():
            # dict_search will return an empty dict "{}" for valueless nodes like
            # "parameters.nolearning" - thus we need to test the nodes existence
            # by using isinstance()
            tmp = dict_search(vyos_key, self.config)
            if isinstance(tmp, dict):
                cmd += f' {iproute2_key}'
            elif tmp != None:
                cmd += f' {iproute2_key} {tmp}'

        self._cmd(cmd.format(**self.config))

    def get_mac(self):
        """ Get a synthetic MAC address. """
        return self.get_mac_synthetic()

    def set_multicast(self, enable):
        """ Change the MULTICAST flag on the device """
        return self.set_interface('multicast', enable)

    def update(self, config):
        """ General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface. """
        # Adjust iproute2 tunnel parameters if necessary
        self._change_options()

        # IP Multicast
        tmp = dict_search('enable_multicast', config)
        value = 'enable' if (tmp != None) else 'disable'
        self.set_multicast(value)

        # call base class first
        super().update(config)
