# Copyright 2019-2022 VyOS maintainers and contributors <maintainers@vyos.io>
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
from vyos.util import call

@Interface.register
class NAT64If(Interface):
    """
    A NAT64 interface is a virtual interface that exchange IPv4 and IPv6 packets.
    """

    iftype = 'nat64'
    definition = {
        **Interface.definition,
        **{
            'section': 'nat64eth',
            'prefixes': ['nat64eth', ],
        },
    }

    def _create(self):
        config_file = f'/run/tayga/{self.ifname}.conf'
        call(f"tayga -c {config_file} --mktun")

    def update(self, config):
        super().update(config)
