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


from vyos.ifconfig.interface import Interface


class GeneveIf(Interface):
    """
    Geneve: Generic Network Virtualization Encapsulation

    For more information please refer to:
    https://tools.ietf.org/html/draft-gross-geneve-00
    https://www.redhat.com/en/blog/what-geneve
    https://developers.redhat.com/blog/2019/05/17/an-introduction-to-linux-virtual-interfaces-tunnels/#geneve
    https://lwn.net/Articles/644938/
    """

    default = {
        'type': 'geneve',
    }

    def __init__(self, ifname, **kargs):
        super().__init__(ifname, **kargs)

    def _create(self):
        cmd = 'ip link add name {} type geneve id {} remote {}' \
            .format(self.config['ifname'], config['vni'], config['remote'])
        self._cmd(cmd)

        # interface is always A/D down. It needs to be enabled explicitly
        self.set_state('down')

    @staticmethod
    def get_config():
        """
        GENEVE interfaces require a configuration when they are added using
        iproute2. This static method will provide the configuration dictionary
        used by this class.

        Example:
        >> dict = GeneveIf().get_config()
        """
        config = {
            'vni': 0,
            'remote': ''
        }
        return config
