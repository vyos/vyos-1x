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

from vyos import ConfigError
from vyos.ifconfig import Interface
from vyos.util import dict_search

@Interface.register
class VXLANIf(Interface):
    """
    The VXLAN protocol is a tunnelling protocol designed to solve the
    problem of limited VLAN IDs (4096) in IEEE 802.1q. With VXLAN the
    size of the identifier is expanded to 24 bits (16777216).

    VXLAN is described by IETF RFC 7348, and has been implemented by a
    number of vendors.  The protocol runs over UDP using a single
    destination port.  This document describes the Linux kernel tunnel
    device, there is also a separate implementation of VXLAN for
    Openvswitch.

    Unlike most tunnels, a VXLAN is a 1 to N network, not just point to
    point. A VXLAN device can learn the IP address of the other endpoint
    either dynamically in a manner similar to a learning bridge, or make
    use of statically-configured forwarding entries.

    For more information please refer to:
    https://www.kernel.org/doc/Documentation/networking/vxlan.txt
    """

    iftype = 'vxlan'
    definition = {
        **Interface.definition,
        **{
            'section': 'vxlan',
            'prefixes': ['vxlan', ],
            'bridgeable': True,
        }
    }

    def _create(self):
        # This table represents a mapping from VyOS internal config dict to
        # arguments used by iproute2. For more information please refer to:
        # - https://man7.org/linux/man-pages/man8/ip-link.8.html
        mapping = {
            'group'                      : 'group',
            'external'                   : 'external',
            'gpe'                        : 'gpe',
            'parameters.ip.dont_fragment': 'df set',
            'parameters.ip.tos'          : 'tos',
            'parameters.ip.ttl'          : 'ttl',
            'parameters.ipv6.flowlabel'  : 'flowlabel',
            'parameters.nolearning'      : 'nolearning',
            'remote'                     : 'remote',
            'source_address'             : 'local',
            'source_interface'           : 'dev',
            'vni'                        : 'id',
        }

        cmd = 'ip link add {ifname} type {type} dstport {port}'
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
        # interface is always A/D down. It needs to be enabled explicitly
        self.set_admin_state('down')
