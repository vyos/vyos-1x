# Copyright 2020-2021 VyOS maintainers and contributors <maintainers@vyos.io>
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
from vyos.util import get_interface_config

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

    def _remove_routes(self, vrf=''):
        # Always delete default routes when interface is removed
        if vrf:
            vrf = f'-c "vrf {vrf}"'
        self._cmd(f'vtysh -c "conf t" {vrf} -c "no ip route 0.0.0.0/0 {self.ifname} tag 210"')
        self._cmd(f'vtysh -c "conf t" {vrf} -c "no ipv6 route ::/0 {self.ifname} tag 210"')

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

        tmp = get_interface_config(self.ifname)
        vrf = ''
        if 'master' in tmp:
            self._remove_routes(tmp['master'])

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

    def update(self, config):
        """ General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface. """

        # remove old routes from an e.g. old VRF assignment
        vrf = ''
        if 'vrf_old' in config:
            vrf = config['vrf_old']
        self._remove_routes(vrf)

        # DHCPv6 PD handling is a bit different on PPPoE interfaces, as we do
        # not require an 'address dhcpv6' CLI option as with other interfaces
        if 'dhcpv6_options' in config and 'pd' in config['dhcpv6_options']:
            self.set_dhcpv6(True)
        else:
            self.set_dhcpv6(False)

        super().update(config)

        if 'default_route' not in config or config['default_route'] == 'none':
            return

        #
        # Set default routes pointing to pppoe interface
        #
        vrf = ''
        sed_opt = '^ip route'

        install_v4 = True
        install_v6 = True

        # generate proper configuration string when VRFs are in use
        if 'vrf' in config:
            tmp = config['vrf']
            vrf = f'-c "vrf {tmp}"'
            sed_opt = f'vrf {tmp}'

        if config['default_route'] == 'auto':
            # only add route if there is no default route present
            tmp = self._cmd(f'vtysh -c "show running-config staticd no-header" | sed -n "/{sed_opt}/,/!/p"')
            for line in tmp.splitlines():
                line = line.lstrip()
                if line.startswith('ip route 0.0.0.0/0'):
                    install_v4 = False
                    continue

                if 'ipv6' in config and line.startswith('ipv6 route ::/0'):
                    install_v6 = False
                    continue

        elif config['default_route'] == 'force':
            # Force means that all static routes are replaced with the ones from this interface
            tmp = self._cmd(f'vtysh -c "show running-config staticd no-header" | sed -n "/{sed_opt}/,/!/p"')
            for line in tmp.splitlines():
                if self.ifname in line:
                    # It makes no sense to remove a route with our interface and the later re-add it.
                    # This will only make traffic disappear - which is a no-no!
                    continue

                line = line.lstrip()
                if line.startswith('ip route 0.0.0.0/0'):
                    self._cmd(f'vtysh -c "conf t" {vrf} -c "no {line}"')

                if 'ipv6' in config and line.startswith('ipv6 route ::/0'):
                    self._cmd(f'vtysh -c "conf t" {vrf} -c "no {line}"')

        if install_v4:
            self._cmd(f'vtysh -c "conf t" {vrf} -c "ip route 0.0.0.0/0 {self.ifname} tag 210"')
        if install_v6 and 'ipv6' in config:
            self._cmd(f'vtysh -c "conf t" {vrf} -c "ipv6 route ::/0 {self.ifname} tag 210"')
