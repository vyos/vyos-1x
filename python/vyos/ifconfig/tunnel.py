# Copyright 2019-2020 VyOS maintainers and contributors <maintainers@vyos.io>
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

from copy import deepcopy

from netaddr import EUI
from netaddr import mac_unix_expanded
from random import getrandbits

from vyos.ifconfig.interface import Interface
from vyos.validate import assert_list

def enable_to_on(value):
    if value == 'enable':
        return 'on'
    if value == 'disable':
        return 'off'
    raise ValueError(f'expect enable or disable but got "{value}"')


@Interface.register
class _Tunnel(Interface):
    """
    _Tunnel: private base class for tunnels
    https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/ip/tunnel.c
    https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/ip/ip6tunnel.c
    """
    definition = {
        **Interface.definition,
        **{
            'section': 'tunnel',
            'prefixes': ['tun',],
            'bridgeable': False,
        },
    }

    # TODO: This is surely used for more than tunnels
    # TODO: could be refactored elsewhere
    _command_set = {**Interface._command_set, **{
        'multicast': {
            'validate': lambda v: assert_list(v, ['enable', 'disable']),
            'convert': enable_to_on,
            'shellcmd': 'ip link set dev {ifname} multicast {value}',
        },
        'allmulticast': {
            'validate': lambda v: assert_list(v, ['enable', 'disable']),
            'convert': enable_to_on,
            'shellcmd': 'ip link set dev {ifname} allmulticast {value}',
        },
    }}

    def __init__(self, ifname, **config):
        self.config = deepcopy(config) if config else {}
        super().__init__(ifname, **config)

    def _create(self):
        create = 'ip tunnel add {ifname} mode {type}'

        # add " option-name option-name-value ..." for all options set
        options = " ".join(["{} {}".format(k, self.config[k])
                            for k in self.options if k in self.config and self.config[k]])
        self._cmd('{} {}'.format(create.format(**self.config), options))
        self.set_admin_state('down')

    def change_options(self):
        change = 'ip tunnel cha {ifname} mode {type}'

        # add " option-name option-name-value ..." for all options set
        options = " ".join(["{} {}".format(k, self.config[k])
                            for k in self.options if k in self.config and self.config[k]])
        self._cmd('{} {}'.format(change.format(**self.config), options))

    @classmethod
    def get_config(cls):
        return dict(zip(cls.options, ['']*len(cls.options)))

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

        # call base class first
        super().update(config)

        # Enable/Disable of an interface must always be done at the end of the
        # derived class to make use of the ref-counting set_admin_state()
        # function. We will only enable the interface if 'up' was called as
        # often as 'down'. This is required by some interface implementations
        # as certain parameters can only be changed when the interface is
        # in admin-down state. This ensures the link does not flap during
        # reconfiguration.
        state = 'down' if 'disable' in config else 'up'
        self.set_admin_state(state)

class GREIf(_Tunnel):
    """
    GRE: Generic Routing Encapsulation

    For more information please refer to:
    RFC1701, RFC1702, RFC2784
    https://tools.ietf.org/html/rfc2784
    https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/ip/link_gre.c
    """

    default = {'type': 'gre'}
    options = ['local', 'remote', 'dev', 'ttl', 'tos', 'key']

# GreTap also called GRE Bridge
class GRETapIf(_Tunnel):
    """
    GRETapIF: GreIF using TAP instead of TUN

    https://en.wikipedia.org/wiki/TUN/TAP
    """

    # no multicast, ttl or tos for gretap

    definition = {
        **_Tunnel.definition,
        **{
            'bridgeable': True,
        },
    }

    default = {'type': 'gretap'}
    options = ['local', 'remote', 'ttl',]

class IP6GREIf(_Tunnel):
    """
    IP6Gre: IPv6 Support for Generic Routing Encapsulation (GRE)

    For more information please refer to:
    https://tools.ietf.org/html/rfc7676
    https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/ip/link_gre6.c
    """

    default = {'type': 'ip6gre'}
    options = ['local', 'remote', 'dev', 'encaplimit',
               'hoplimit', 'tclass', 'flowlabel']

class IPIPIf(_Tunnel):
    """
    IPIP: IP Encapsulation within IP

    For more information please refer to:
    https://tools.ietf.org/html/rfc2003
    """

    # IPIP does not allow to pass multicast, unlike GRE
    # but the interface itself can be set with multicast

    default = {'type': 'ipip'}
    options = ['local', 'remote', 'dev', 'ttl', 'tos', 'key']

class IPIP6If(_Tunnel):
    """
    IPIP6: IPv4 over IPv6 tunnel

    For more information please refer to:
    https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/ip/link_ip6tnl.c
    """

    default = {'type': 'ipip6'}
    options = ['local', 'remote', 'dev', 'encaplimit',
               'hoplimit', 'tclass', 'flowlabel']

class IP6IP6If(IPIP6If):
    """
    IP6IP6: IPv6 over IPv6 tunnel

    For more information please refer to:
    https://tools.ietf.org/html/rfc2473
    """
    default = {'type': 'ip6ip6'}


class SitIf(_Tunnel):
    """
    Sit: Simple Internet Transition

    For more information please refer to:
    https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/ip/link_iptnl.c
    """

    default = {'type': 'sit'}
    options = ['local', 'remote', 'dev', 'ttl', 'tos', 'key']

class Sit6RDIf(SitIf):
    """
    Sit6RDIf: Simple Internet Transition with 6RD

    https://en.wikipedia.org/wiki/IPv6_rapid_deployment
    """
    # TODO: check if key can really be used with 6RD
    options = ['remote', 'ttl', 'tos', 'key', '6rd-prefix', '6rd-relay-prefix']

    def _create(self):
        # do not call _Tunnel.create, building fully here

        create = 'ip tunnel add {ifname} mode {type} remote {remote}'
        self._cmd(create.format(**self.config))
        self.set_interface('state','down')

        set6rd = 'ip tunnel 6rd dev {ifname} 6rd-prefix {6rd-prefix}'
        if '6rd-relay-prefix' in self.config:
            set6rd += ' 6rd-relay-prefix {6rd-relay-prefix}'
        self._cmd(set6rd.format(**self.config))
