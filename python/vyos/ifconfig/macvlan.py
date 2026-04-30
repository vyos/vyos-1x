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
from vyos.ifconfig import BridgeIf
from vyos.utils.network import get_interface_config
from vyos.utils.network import interface_exists
from vyos.utils.network import split_interface_vlans

@Interface.register
class MACVLANIf(Interface):
    """
    Abstraction of a Linux MACvlan interface
    """
    definition = {
        **Interface.definition,
        **{
            'section': 'pseudo-ethernet',
            'prefixes': ['peth', ],
        },
    }

    def _create(self):
        """
        Create MACvlan interface in OS kernel. Interface is administrative
        down by default.
        """
        # please do not change the order when assembling the command
        cmd = 'ip link add {ifname} link {source_interface} type macvlan mode {mode}'
        self._cmd(cmd.format(**self.config))

        # interface is always A/D down. It needs to be enabled explicitly
        self.set_admin_state('down')

    def _get_bridge_by_source(self, source_interface: str) -> BridgeIf | None:
        """
        Resolve a source interface name to its root BridgeIf object.

        Handles plain bridge names (e.g. 'br0') and bridge sub-interfaces
        with one or two VLAN suffixes (e.g. 'br0.100', 'br0.100.200').
        """

        bridge = None
        if source_interface.startswith('br'):
            # We only need the root bridge name, so unpack with *_ to
            # discard the VLAN parts.
            bridge_ifname, *_ = split_interface_vlans(source_interface)
            if interface_exists(bridge_ifname):
                bridge = BridgeIf(bridge_ifname)

        return bridge

    def _create_anycast_gateway(self, source_interface, mac):
        """Install a local FDB entry on the parent bridge for the anycast MAC"""

        if source_interface and mac:
            bridge = self._get_bridge_by_source(source_interface)
            if bridge:
                bridge.add_local_fdb_entry(mac)

    def _delete_anycast_gateway(self, source_interface, mac):
        """Remove the local FDB entry from the parent bridge for the anycast MAC"""

        if source_interface and mac:
            bridge = self._get_bridge_by_source(source_interface)
            if bridge:
                try:
                    bridge.del_local_fdb_entry(mac)
                except OSError:
                    pass  # Bridge may already be gone, that is fine

    def update(self, config):
        # Always attempt to remove any existing anycast FDB entry before
        # applying the new config. It reads the currently live
        # state of the interface (before update).
        self._delete_anycast_gateway(self.get_source_interface(), self.get_mac())

        # Apply all standard interface configuration
        super().update(config)

        # After the interface is fully updated, install the new FDB entry if
        # anycast-gateway is set in the incoming config.
        if 'anycast_gateway' in self.config:
            self._create_anycast_gateway(
                self.config.get('source_interface'), self.get_mac()
            )

    def remove(self, skip_delete=False):
        # Before tearing down the MACVLAN interface, clean up the anycast
        # gateway FDB entry from the parent bridge.
        self._delete_anycast_gateway(
            self.get_source_interface(), self.get_mac()
        )

        return super().remove(skip_delete=skip_delete)

    def set_mode(self, mode):
        cmd = f'ip link set dev {self.ifname} type macvlan mode {mode}'
        return self._cmd(cmd)

    def get_source_interface(self):
        interface_config = get_interface_config(self.ifname)
        return interface_config['link'] if interface_config is not None else None
