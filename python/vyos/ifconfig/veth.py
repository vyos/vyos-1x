# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
from vyos.utils.dict import dict_search
from vyos.utils.network import get_interface_config

@Interface.register
class VethIf(Interface):
    """
    Abstraction of a Linux veth interface
    """
    definition = {
        **Interface.definition,
        **{
            'section': 'virtual-ethernet',
            'prefixes': ['veth', ],
            'bridgeable': True,
        },
    }

    def _create(self):
        """
        Create veth interface in OS kernel. Interface is administrative
        down by default.
        """
        # check before create, as we have 2 veth interfaces in our CLI
        # interface virtual-ethernet veth0 peer-name 'veth1'
        # interface virtual-ethernet veth1 peer-name 'veth0'
        #
        # but iproute2 creates the pair with one command:
        # ip link add vet0 type veth peer name veth1
        if self.exists(self.config['peer_name']):
            return

        # create virtual-ethernet interface
        cmd = f'ip link add {self.ifname} type veth'
        cmd += f' peer name {self.config["peer_name"]}'
        self._cmd(cmd)

        # interface is always A/D down. It needs to be enabled explicitly
        self.set_admin_state('down')

    def remove(self):
        # The oddity with virtual-ethernet pairs is, if you delete one - the OS
        # Kernel will immediately delete the other interface, leaving no
        # possibility to properly shutdown the peer-interface.
        #
        # We deconfigure the second veth pair interface during deletion, but
        # skip it's actual call to "ip link del dev ..."
        tmp = get_interface_config(self.ifname)
        peer = tmp.get('link', dict_search('linkinfo.info_kind', tmp))
        if peer != None:
            Interface(peer).remove(skip_delete=True)

        # always forward to the base class
        super().remove()
