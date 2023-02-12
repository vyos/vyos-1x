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

@Interface.register
class LoopbackIf(Interface):
    """
    The loopback device is a special, virtual network interface that your router
    uses to communicate with itself.
    """
    _persistent_addresses = ['127.0.0.1/8', '::1/128']
    iftype = 'loopback'
    definition = {
        **Interface.definition,
        **{
            'section': 'loopback',
            'prefixes': ['lo', ],
            'bridgeable': True,
        }
    }

    def remove(self):
        """
        Loopback interface can not be deleted from operating system. We can
        only remove all assigned IP addresses.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> i = LoopbackIf('lo').remove()
        """
        # remove all assigned IP addresses from interface
        for addr in self.get_addr():
            if addr in self._persistent_addresses:
                # Do not allow deletion of the default loopback addresses as
                # this will cause weird system behavior like snmp/ssh no longer
                # operating as expected, see https://vyos.dev/T2034.
                continue

            self.del_addr(addr)

    def update(self, config):
        """ General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface. """

        address = config.get('address', [])
        # We must ensure that the loopback addresses are never deleted from the system
        for tmp in self._persistent_addresses:
            if tmp not in address:
                address.append(tmp)

        # Update IP address entry in our dictionary
        config.update({'address' : address})

        # call base class
        super().update(config)
