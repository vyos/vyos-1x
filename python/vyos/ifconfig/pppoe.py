# Copyright 2020-2022 VyOS maintainers and contributors <maintainers@vyos.io>
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
from vyos.utils.assertion import assert_range
from vyos.utils.network import get_interface_config

@Interface.register
class PPPoEIf(Interface):
    iftype = 'pppoe'
    definition = {
        **Interface.definition,
        **{
            'section': 'pppoe',
            'prefixes': ['pppoe', ],
        },
    }

    _sysfs_get = {
        **Interface._sysfs_get,**{
            'accept_ra_defrtr': {
                'location': '/proc/sys/net/ipv6/conf/{ifname}/accept_ra_defrtr',
            }
        }
    }

    _sysfs_set = {**Interface._sysfs_set, **{
        'accept_ra_defrtr': {
            'validate': lambda value: assert_range(value, 0, 2),
            'location': '/proc/sys/net/ipv6/conf/{ifname}/accept_ra_defrtr',
        },
    }}

    def _remove_routes(self, vrf=None):
        # Always delete default routes when interface is removed
        vrf_cmd = ''
        if vrf:
            vrf_cmd = f'-c "vrf {vrf}"'
        self._cmd(f'vtysh -c "conf t" {vrf_cmd} -c "no ip route 0.0.0.0/0 {self.ifname} tag 210"')
        self._cmd(f'vtysh -c "conf t" {vrf_cmd} -c "no ipv6 route ::/0 {self.ifname} tag 210"')

    def remove(self):
        """
        Remove interface from operating system. Removing the interface
        deconfigures all assigned IP addresses and clear possible DHCP(v6)
        client processes.
        Example:
        >>> from vyos.ifconfig import Interface
        >>> i = Interface('pppoe0')
        >>> i.remove()
        """
        vrf = None
        tmp = get_interface_config(self.ifname)
        if 'master' in tmp:
            vrf = tmp['master']
        self._remove_routes(vrf)

        # remove bond master which places members in disabled state
        super().remove()

    def _create(self):
        # we can not create this interface as it is managed outside
        pass

    def _delete(self):
        # we can not create this interface as it is managed outside
        pass

    def del_addr(self, addr):
        # we can not create this interface as it is managed outside
        pass

    def get_mac(self):
        """ Get a synthetic MAC address. """
        return self.get_mac_synthetic()

    def set_accept_ra_defrtr(self, enable):
        """
        Learn default router in Router Advertisement.
        1: enabled
        0: disable

        Example:
        >>> from vyos.ifconfig import PPPoEIf
        >>> PPPoEIf('pppoe1').set_accept_ra_defrtr(0)
        """
        tmp = self.get_interface('accept_ra_defrtr')
        if tmp == enable:
            return None
        self.set_interface('accept_ra_defrtr', enable)

    def update(self, config):
        """ General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface. """

        # Cache the configuration - it will be reused inside e.g. DHCP handler
        # XXX: maybe pass the option via __init__ in the future and rename this
        # method to apply()?
        #
        # We need to copy this from super().update() as we utilize self.set_dhcpv6()
        # before this is done by the base class.
        self._config = config

        # remove old routes from an e.g. old VRF assignment
        if 'shutdown_required':
            vrf = None
            tmp = get_interface_config(self.ifname)
            if 'master' in tmp:
                vrf = tmp['master']
            self._remove_routes(vrf)

        # DHCPv6 PD handling is a bit different on PPPoE interfaces, as we do
        # not require an 'address dhcpv6' CLI option as with other interfaces
        if 'dhcpv6_options' in config and 'pd' in config['dhcpv6_options']:
            self.set_dhcpv6(True)
        else:
            self.set_dhcpv6(False)

        super().update(config)

        # generate proper configuration string when VRFs are in use
        vrf = ''
        if 'vrf' in config:
            tmp = config['vrf']
            vrf = f'-c "vrf {tmp}"'

        # learn default router in Router Advertisement.
        tmp = '0' if 'no_default_route' in config else '1'
        self.set_accept_ra_defrtr(tmp)

        if 'no_default_route' not in config:
            # Set default route(s) pointing to PPPoE interface
            distance = config['default_route_distance']
            self._cmd(f'vtysh -c "conf t" {vrf} -c "ip route 0.0.0.0/0 {self.ifname} tag 210 {distance}"')
            if 'ipv6' in config:
                self._cmd(f'vtysh -c "conf t" {vrf} -c "ipv6 route ::/0 {self.ifname} tag 210 {distance}"')
