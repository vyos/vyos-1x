# Copyright 2020-2023 VyOS maintainers and contributors <maintainers@vyos.io>
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

@Interface.register
class MACsecIf(Interface):
    """
    MACsec is an IEEE standard (IEEE 802.1AE) for MAC security, introduced in
    2006. It defines a way to establish a protocol independent connection
    between two hosts with data confidentiality, authenticity and/or integrity,
    using GCM-AES-128. MACsec operates on the Ethernet layer and as such is a
    layer 2 protocol, which means it's designed to secure traffic within a
    layer 2 network, including DHCP or ARP requests. It does not compete with
    other security solutions such as IPsec (layer 3) or TLS (layer 4), as all
    those solutions are used for their own specific use cases.
    """
    iftype = 'macsec'
    definition = {
        **Interface.definition,
        **{
            'section': 'macsec',
            'prefixes': ['macsec', ],
        },
    }

    def _create(self):
        """
        Create MACsec interface in OS kernel. Interface is administrative
        down by default.
        """

        # create tunnel interface
        cmd  = 'ip link add link {source_interface} {ifname} type {type}'.format(**self.config)
        cmd += f' cipher {self.config["security"]["cipher"]}'

        if 'encrypt' in self.config["security"]:
            cmd += ' encrypt on'

        self._cmd(cmd)

        # Check if using static keys
        if 'static' in self.config["security"]:
            # Set static TX key
            cmd = 'ip macsec add {ifname} tx sa 0 pn 1 on key 00'.format(**self.config)
            cmd += f' {self.config["security"]["static"]["key"]}'
            self._cmd(cmd)

            for peer, peer_config in self.config["security"]["static"]["peer"].items():
                if 'disable' in peer_config:
                    continue

                # Create the address
                cmd = 'ip macsec add {ifname} rx port 1 address'.format(**self.config)
                cmd += f' {peer_config["mac"]}'
                self._cmd(cmd)
                # Add the encryption key to the address
                cmd += f' sa 0 pn 1 on key 01 {peer_config["key"]}'
                self._cmd(cmd)

        # interface is always A/D down. It needs to be enabled explicitly
        self.set_admin_state('down')
