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


@Interface.register
class LoopbackIf(Interface):
    """
    The loopback device is a special, virtual network interface that your router
    uses to communicate with itself.
    """
    _persistent_addresses = ['127.0.0.1/8', '::1/128']
    default = {
        'type': 'loopback',
    }
    definition = {
        **Interface.definition,
        **{
            'section': 'loopback',
            'prefixes': ['lo', ],
            'bridgeable': True,
        }
    }

    name = 'loopback'

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
                # operating as expected, see https://phabricator.vyos.net/T2034.
                continue

            self.del_addr(addr)

    def update(self, config):
        """ General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface. """

        addr = config.get('address', [])
        # We must ensure that the loopback addresses are never deleted from the system
        addr += self._persistent_addresses

        # Update IP address entry in our dictionary
        config.update({'address' : addr})

        # call base class
        super().update(config)

        # Enable/Disable of an interface must always be done at the end of the
        # derived class to make use of the ref-counting set_admin_state()
        # function. We will only enable the interface if 'up' was called as
        # often as 'down'. This is required by some interface implementations
        # as certain parameters can only be changed when the interface is
        # in admin-down state. This ensures the link does not flap during
        # reconfiguration.
        state = 'down' if 'disable' in config else 'up'
        self.set_admin_state(state)
