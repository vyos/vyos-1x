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

# https://developers.redhat.com/blog/2019/05/17/an-introduction-to-linux-virtual-interfaces-tunnels/
# https://community.hetzner.com/tutorials/linux-setup-gre-tunnel


from copy import deepcopy

from vyos.ifconfig.interface import Interface
from vyos.ifconfig.afi import IP4, IP6
from vyos.validate import assert_list

def enable_to_on(value):
    if value == 'enable':
        return 'on'
    if value == 'disable':
        return 'off'
    raise ValueError(f'expect enable or disable but got "{value}"')



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
            'bridgeable': True,
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

    # use for "options" and "updates"
    # If an key is only in the options list, it can only be set at creation time
    # the create comand will only be make using the key in options

    # If an option is in the updates list, it can be updated
    # upon, the creation, all key not yet applied will be updated

    # multicast/allmulticast can not be part of the create command

    # options matrix:
    # with ip = 4,     we have multicast
    # wiht ip = 6,     nothing
    # with tunnel = 4, we have tos, ttl, key
    # with tunnel = 6, we have encaplimit, hoplimit, tclass, flowlabel

    # TODO: For multicast, it is allowed on IP6IP6 and Sit6RD
    # TODO: to match vyatta but it should be checked for correctness

    updates = []

    create = ''
    change = ''
    delete = ''

    ip = []     # AFI of the families which can be used in the tunnel
    tunnel = 0  # invalid - need to be set by subclasses

    def __init__(self, ifname, **config):
        self.config = deepcopy(config) if config else {}
        super().__init__(ifname, **config)

    def _create(self):
        # add " option-name option-name-value ..." for all options set
        options = " ".join(["{} {}".format(k, self.config[k])
                            for k in self.options if k in self.config and self.config[k]])
        self._cmd('{} {}'.format(self.create.format(**self.config), options))
        self.set_interface('state', 'down')

    def _delete(self):
        self.set_interface('state', 'down')
        cmd = self.delete.format(**self.config)
        return self._cmd(cmd)

    def set_interface(self, option, value):
        try:
            return Interface.set_interface(self, option, value)
        except Exception:
            pass

        if value == '':
            # remove the value so that it is not used
            self.config.pop(option, '')

        if self.change:
            self._cmd('{} {} {}'.format(
                self.change.format(**self.config), option, value))
        return True

    @classmethod
    def get_config(cls):
        return dict(zip(cls.options, ['']*len(cls.options)))


class GREIf(_Tunnel):
    """
    GRE: Generic Routing Encapsulation

    For more information please refer to:
    RFC1701, RFC1702, RFC2784
    https://tools.ietf.org/html/rfc2784
    https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/ip/link_gre.c
    """

    ip = [IP4, IP6]
    tunnel = IP4

    default = {'type': 'gre'}
    required = ['local', ]  # mGRE is a GRE without remote endpoint

    options = ['local', 'remote', 'ttl', 'tos', 'key']
    updates = ['local', 'remote', 'ttl', 'tos',
               'multicast', 'allmulticast']

    create = 'ip tunnel add {ifname} mode {type}'
    change = 'ip tunnel cha {ifname}'
    delete = 'ip tunnel del {ifname}'


# GreTap also called GRE Bridge
class GRETapIf(_Tunnel):
    """
    GRETapIF: GreIF using TAP instead of TUN

    https://en.wikipedia.org/wiki/TUN/TAP
    """

    # no multicast, ttl or tos for gretap

    ip = [IP4, ]
    tunnel = IP4

    default = {'type': 'gretap'}
    required = ['local', ]

    options = ['local', 'remote', ]
    updates = []

    create = 'ip link add {ifname} type {type}'
    change = ''
    delete = 'ip link del {ifname}'


class IP6GREIf(_Tunnel):
    """
    IP6Gre: IPv6 Support for Generic Routing Encapsulation (GRE)

    For more information please refer to:
    https://tools.ietf.org/html/rfc7676
    https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/ip/link_gre6.c
    """

    ip = [IP4, IP6]
    tunnel = IP6

    default = {'type': 'ip6gre'}
    required = ['local', 'remote']

    options = ['local', 'remote', 'encaplimit',
               'hoplimit', 'tclass', 'flowlabel']
    updates = ['local', 'remote', 'encaplimit',
               'hoplimit', 'tclass', 'flowlabel',
               'multicast', 'allmulticast']

    create = 'ip tunnel add {ifname} mode {type}'
    change = 'ip tunnel cha {ifname} mode {type}'
    delete = 'ip tunnel del {ifname}'

    # using "ip tunnel change" without using "mode" causes errors
    # sudo ip tunnel add tun100 mode ip6gre local ::1 remote 1::1
    # sudo ip tunnel cha tun100 hoplimit 100
    # *** stack smashing detected ** *: < unknown > terminated
    # sudo ip tunnel cha tun100 local: : 2
    # Error: an IP address is expected rather than "::2"
    # works if mode is explicit


class IPIPIf(_Tunnel):
    """
    IPIP: IP Encapsulation within IP

    For more information please refer to:
    https://tools.ietf.org/html/rfc2003
    """

    # IPIP does not allow to pass multicast, unlike GRE
    # but the interface itself can be set with multicast

    ip = [IP4,]
    tunnel = IP4

    default = {'type': 'ipip'}
    required = ['local', 'remote']

    options = ['local', 'remote', 'ttl', 'tos', 'key']
    updates = ['local', 'remote', 'ttl', 'tos',
               'multicast', 'allmulticast']

    create = 'ip tunnel add {ifname} mode {type}'
    change = 'ip tunnel cha {ifname}'
    delete = 'ip tunnel del {ifname}'


class IPIP6If(_Tunnel):
    """
    IPIP6: IPv4 over IPv6 tunnel

    For more information please refer to:
    https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/ip/link_ip6tnl.c
    """

    ip = [IP4,]
    tunnel = IP6

    default = {'type': 'ipip6'}
    required = ['local', 'remote']

    options = ['local', 'remote', 'encaplimit',
               'hoplimit', 'tclass', 'flowlabel']
    updates = ['local', 'remote', 'encaplimit',
               'hoplimit', 'tclass', 'flowlabel',
               'multicast', 'allmulticast']

    create = 'ip -6 tunnel add {ifname} mode {type}'
    change = 'ip -6 tunnel cha {ifname}'
    delete = 'ip -6 tunnel del {ifname}'


class IP6IP6If(IPIP6If):
    """
    IP6IP6: IPv6 over IPv6 tunnel

    For more information please refer to:
    https://tools.ietf.org/html/rfc2473
    """

    ip = [IP6,]

    default = {'type': 'ip6ip6'}


class SitIf(_Tunnel):
    """
    Sit: Simple Internet Transition

    For more information please refer to:
    https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/ip/link_iptnl.c
    """

    ip = [IP6, IP4]
    tunnel = IP4

    default = {'type': 'sit'}
    required = ['local', 'remote']

    options = ['local', 'remote', 'ttl', 'tos', 'key']
    updates = ['local', 'remote', 'ttl', 'tos',
               'multicast', 'allmulticast']

    create = 'ip tunnel add {ifname} mode {type}'
    change = 'ip tunnel cha {ifname}'
    delete = 'ip tunnel del {ifname}'


class Sit6RDIf(SitIf):
    """
    Sit6RDIf: Simple Internet Transition with 6RD

    https://en.wikipedia.org/wiki/IPv6_rapid_deployment
    """

    ip = [IP6,]

    required = ['remote', '6rd-prefix']

    # TODO: check if key can really be used with 6RD
    options = ['remote', 'ttl', 'tos', 'key', '6rd-prefix', '6rd-relay-prefix']
    updates = ['remote', 'ttl', 'tos',
               'multicast', 'allmulticast']

    def _create(self):
        # do not call _Tunnel.create, building fully here

        create = 'ip tunnel add {ifname} mode {type} remote {remote}'
        self._cmd(create.format(**self.config))
        self.set_interface('state','down')

        set6rd = 'ip tunnel 6rd dev {ifname} 6rd-prefix {6rd-prefix}'
        if '6rd-relay-prefix' in self.config:
            set6rd += ' 6rd-relay-prefix {6rd-relay-prefix}'
        self._cmd(set6rd.format(**self.config))
