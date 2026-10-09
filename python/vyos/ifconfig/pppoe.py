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
from vyos.template import is_ipv6
from vyos.utils.assertion import assert_range
from vyos.utils.dict import dict_search
from vyos.utils.process import cmdl
from vyos.utils.process import get_wrapper
from vyos.utils.network import mac2eui64

@Interface.register
class PPPoEIf(Interface):
    definition = {
        **Interface.definition,
        **{
            'section': 'pppoe',
            'prefixes': ['pppoe', ],
        },
    }

    # T9060: the IPv6 interface identifier of a PPP link is negotiated with
    # the peer via IPV6CP (RFC 5072) - see Interface._ipv6_default_link_local
    _ipv6_default_link_local = False

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

    def _create(self):
        # we cannot create this interface as it is managed outside
        pass

    def _delete(self):
        # we cannot create this interface as it is managed outside
        pass

    def del_addr(self, addr):
        # we cannot create this interface as it is managed outside
        pass

    def del_ipv6_eui64_address(self, prefix):
        """
        del_addr() is a NOOP as the addresses are managed by pppd. The EUI-64
        link-local address was added by VyOS itself, so use the generic
        implementation to clean it off an already established session.
        """
        if is_ipv6(prefix):
            eui64 = mac2eui64(self.get_mac(), prefix)
            prefixlen = prefix.split('/')[1]
            super().del_addr(f'{eui64}/{prefixlen}')

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
        """ General helper function which works on a dictionary retrieved by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when working
        on any interface. """

        # Cache the configuration - it will be reused inside e.g. DHCP handler
        # XXX: maybe pass the option via __init__ in the future and rename this
        # method to apply()?
        #
        # We need to copy this from super().update() as we utilize self.set_dhcpv6()
        # before this is done by the base class.
        self._config = config

        # DHCPv6 PD handling is a bit different on PPPoE interfaces, as we do
        # not require an 'address dhcpv6' CLI option as with other interfaces
        if 'dhcpv6_options' in config and 'pd' in config['dhcpv6_options']:
            self.set_dhcpv6(True)
        else:
            self.set_dhcpv6(False)

        super().update(config)

        vrf = config.get('vrf')

        # learn default router in Router Advertisement.
        tmp = '0' if 'no_default_route' in config else '1'
        self.set_accept_ra_defrtr(tmp)

        # Default route(s) pointing to the PPPoE interface are rendered by
        # vyos.frrender.get_pppoe_interfaces() at the end of every commit

        # Kick a Router Solicitation when IPv6 is up. This is best effort -
        # the peer may answer late or not at all
        if dict_search('ipv6.address.autoconf', config) is not None:
            # systemd-run(1) only asks PID 1 to start the transient unit, so
            # rdisc6(8) does not inherit our VRF context - it has to be entered
            # inside the unit itself
            wrapper = get_wrapper(vrf, None)
            description = f'VyOS IPv6 Router Solicitation on {self.ifname}'
            cmdl(['systemd-run', '--quiet', '--collect',
                  f'--description={description}'] + wrapper +
                 ['rdisc6', '--single', '--retry', '3', self.ifname], self.debug)
