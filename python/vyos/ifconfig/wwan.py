# Copyright 2021 VyOS maintainers and contributors <maintainers@vyos.io>
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

import time
from vyos.ifconfig.interface import Interface
from vyos.utils.dict import dict_search

@Interface.register
class WWANIf(Interface):
    definition = {
        **Interface.definition,
        **{
            'section': 'wwan',
            'prefixes': ['wwan', ],
            'eternal': 'wwan[0-9]+$',
        },
    }

    def remove(self):
        """
        Remove interface from config. Removing the interface deconfigures all
        assigned IP addresses.
        Example:
        >>> from vyos.ifconfig import WWANIf
        >>> i = WWANIf('wwan0')
        >>> i.remove()
        """

        if self.exists(self.ifname):
            # interface is placed in A/D state when removed from config! It
            # will remain visible for the operating system.
            self.set_admin_state('down')

        super().remove()

    def update(self, config):
        '''Perform interface setup for wwan'''
        super().update(config)

        # PSL: If "ipv6 address autoconf" is set switch to address mode 3,
        # else use the VyOS default of 1. This enables IPv6 since those
        # addresses will come from the cell network via the modem.
        sysfs_agm = f'/proc/sys/net/ipv6/conf/{self.ifname}/addr_gen_mode'
        if dict_search('ipv6.address.autoconf', config) is None:
            addr_gen_mode = '1'
        else:
            addr_gen_mode = '3'

        if self._read_sysfs(sysfs_agm) != addr_gen_mode:
            # Needs update
            self._write_sysfs(sysfs_agm, addr_gen_mode)
            if addr_gen_mode == '3' and self.get_admin_state() == 'up':
                # Have to bounce the iface to get an IPv6 global addr
                for state in ('down', 'up'):
                    time.sleep(.1)
                    self.set_admin_state(state)
