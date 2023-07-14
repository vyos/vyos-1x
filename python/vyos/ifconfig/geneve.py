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

from vyos.ifconfig import Interface
from vyos.utils.dict import dict_search

@Interface.register
class GeneveIf(Interface):
    """
    Geneve: Generic Network Virtualization Encapsulation

    For more information please refer to:
    https://tools.ietf.org/html/draft-gross-geneve-00
    https://www.redhat.com/en/blog/what-geneve
    https://developers.redhat.com/blog/2019/05/17/an-introduction-to-linux-virtual-interfaces-tunnels/#geneve
    https://lwn.net/Articles/644938/
    """
    iftype = 'geneve'
    definition = {
        **Interface.definition,
        **{
            'section': 'geneve',
            'prefixes': ['gnv', ],
            'bridgeable': True,
        }
    }

    def _create(self):
        # This table represents a mapping from VyOS internal config dict to
        # arguments used by iproute2. For more information please refer to:
        # - https://man7.org/linux/man-pages/man8/ip-link.8.html
        mapping = {
            'parameters.ip.df'           : 'df',
            'parameters.ip.tos'          : 'tos',
            'parameters.ip.ttl'          : 'ttl',
            'parameters.ip.innerproto'   : 'innerprotoinherit',
            'parameters.ipv6.flowlabel'  : 'flowlabel',
        }

        cmd = 'ip link add name {ifname} type {type} id {vni} remote {remote}'
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
