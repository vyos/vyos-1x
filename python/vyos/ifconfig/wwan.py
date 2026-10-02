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

from json import loads

from vyos.hostsd_client import Client as hostsd_client
from vyos.hostsd_client import VyOSHostsdError
from vyos.ifconfig.interface import Interface
from vyos.utils.dict import dict_search
from vyos.utils.misc import wait_for
from vyos.utils.network import get_interface_address
from vyos.utils.network import is_intf_addr_assigned
from vyos.utils.process import cmdl
from vyos.utils.process import is_systemd_service_active
from vyos.utils.wwan import modem_index

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

    def _create(self):
        # we cannot create this interface as it is managed by the Kernel
        pass

    def update(self, config):
        # The kernel rejects a route via the bearer's gateway until the
        # interface is up, which only happens at the end of super().update() -
        # queue it here and apply after, like sibling PPPoEIf does.
        self._pending_bearer_routes = {}
        try:
            super().update(config)
            for family, (gateway, distance) in self._pending_bearer_routes.items():
                self._install_bearer_route(family, gateway, distance)
        finally:
            # Drop the queue so a later direct add_addr() call installs its
            # route immediately instead of silently doing nothing.
            del self._pending_bearer_routes

    def _get_active_bearer(self):
        """Return the mmcli --output-json dict for this interface's
        connected ModemManager bearer, or None. Matches on status.connected
        rather than bearers[0], since a stale disconnected bearer can
        linger alongside the current one."""
        modem = modem_index(self.ifname)
        if modem is None:
            return None
        try:
            modem_info = loads(cmdl(['mmcli', '--modem', modem, '--output-json']))
        except (OSError, ValueError):
            return None
        bearers = dict_search('modem.generic.bearers', modem_info) or []
        for bearer_path in bearers:
            bearer_id = bearer_path.rsplit('/', 1)[-1]
            try:
                bearer = loads(cmdl(['mmcli', '--bearer', bearer_id, '--output-json']))
            except (OSError, ValueError):
                continue
            if dict_search('bearer.status.connected', bearer) == 'yes':
                return bearer
        return None

    def _wait_for_bearer_method(self, family):
        # A bearer can report "connected" before its ipv4-config/ipv6-config
        # is populated over D-Bus - retry briefly rather than mistaking that
        # delay for "no static config".
        result = {}

        def _ready():
            result['bearer'] = self._get_active_bearer()
            result['method'] = (
                dict_search(f'bearer.{family}-config.method', result['bearer'])
                if result['bearer']
                else None
            )
            return result['method'] is not None

        wait_for(_ready, interval=0.5, timeout=5)
        return result['bearer'], result['method']

    def add_addr(self, addr: str, vrf_changed: bool = False) -> bool:
        if addr not in ('dhcp', 'dhcpv6'):
            return super().add_addr(addr, vrf_changed=vrf_changed)

        family = 'ipv4' if addr == 'dhcp' else 'ipv6'

        bearer, method = self._wait_for_bearer_method(family)

        if method in (None, '', '--', 'dhcp'):
            if method != 'dhcp':
                # Bearer is gone or not up yet: clear any DNS a previous
                # static bearer left under this tag, since the DHCP(v6)
                # client below only replaces it on a successful lease.
                self._set_hostsd_name_servers(family, None)
            return super().add_addr(addr, vrf_changed=vrf_changed)

        # method == 'static' (the common case for QMI raw-ip modems): apply
        # the bearer's own address/gateway/DNS directly, since a DHCP(v6)
        # client would never get a reply from it.
        return self._apply_bearer_address(bearer, family)

    def set_ipv6_autoconf(self, autoconf):
        if autoconf == '0':
            result = super().set_ipv6_autoconf(autoconf)
            # Called with '0' on every commit where autoconf isn't
            # configured, not just on disable - skip the sweep if dhcpv6
            # owns the address instead, which cleans up after itself.
            if 'dhcpv6' not in (self.config.get('address') or []):
                self._clear_bearer_address('ipv6')
            return result

        # Same idea as add_addr(): a modem resolving IPv6 over the air sends
        # no RA traffic for the kernel to autoconf from, so apply the
        # bearer's result directly. Falls through unchanged for a modem that
        # genuinely needs host-side SLAAC (e.g. Intel XMM-based).
        bearer, method = self._wait_for_bearer_method('ipv6')

        if method in (None, '', '--', 'dhcp'):
            if method != 'dhcp':
                self._set_hostsd_name_servers('ipv6', None)
            return super().set_ipv6_autoconf(autoconf)

        return self._apply_bearer_address(bearer, 'ipv6')

    def del_addr(self, addr: str) -> bool:
        if addr not in ('dhcp', 'dhcpv6'):
            return super().del_addr(addr)

        # Let a real DHCP(v6) client release its lease and clean up its own
        # tag first; only then sweep anything a static bearer applied,
        # since at most one of the two ever had the address.
        result = super().del_addr(addr)
        family = 'ipv4' if addr == 'dhcp' else 'ipv6'
        self._clear_bearer_address(family)
        return result

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

        # flush_addrs() clears the addresses but bypasses del_addr(), so it
        # never runs the vyos-hostsd tag cleanup a static bearer needs.
        self._clear_bearer_address('ipv4')
        self._clear_bearer_address('ipv6')

        super().remove()

    def _apply_bearer_address(self, bearer, family) -> bool:
        prefix = f'bearer.{family}-config'
        address = dict_search(f'{prefix}.address', bearer)
        plen = dict_search(f'{prefix}.prefix', bearer)
        if not address or not plen:
            return False
        cidr = f'{address}/{plen}'

        # A reconnect can negotiate a different address, and there's no
        # config-tree entry for a bearer's address to diff against - remove
        # any stale one of this family except a static address the operator
        # configured directly.
        configured = set(self.config.get('address') or [])
        inet_family = 'inet' if family == 'ipv4' else 'inet6'
        current = get_interface_address(self.ifname) or {}
        for addr_info in current.get('addr_info', []):
            if (
                addr_info.get('family') != inet_family
                or addr_info.get('scope') == 'link'
            ):
                continue
            old_cidr = f"{addr_info['local']}/{addr_info['prefixlen']}"
            if old_cidr != cidr and old_cidr not in configured:
                self.del_addr(old_cidr)

        if not is_intf_addr_assigned(self.ifname, cidr):
            tmp = ['ip', 'addr', 'add', cidr, 'dev', self.ifname]
            if family == 'ipv4':
                tmp += ['brd', '+']
            self._cmdl(tmp)
            self._addr.append(cidr)

        self._apply_bearer_route(bearer, family)
        self._apply_bearer_dns(bearer, family)
        return True

    def _apply_bearer_route(self, bearer, family):
        gateway = dict_search(f'bearer.{family}-config.gateway', bearer)
        # IPv6 has no no-default-route/default-route-distance leaf (routes
        # normally come from RA, not DHCPv6) - only IPv4 uses these.
        no_default_route = (
            family == 'ipv4'
            and dict_search('dhcp_options.no_default_route', self.config) is not None
        )
        if not gateway or no_default_route:
            # Withdraw a route a previous commit may have installed; a
            # bearer's gateway isn't tracked in the config tree either.
            self._remove_bearer_route(family)
            return

        distance = None
        if family == 'ipv4':
            distance = dict_search('dhcp_options.default_route_distance', self.config)
        if not hasattr(self, '_pending_bearer_routes'):
            # Called directly outside update() - install now, since nothing
            # will flush a queued route.
            self._install_bearer_route(family, gateway, distance)
            return
        self._pending_bearer_routes[family] = (gateway, distance)

    def _install_bearer_route(self, family, gateway, distance):
        # Table selection needs an explicit vrf keyword after "route
        # replace" - enslaving the device to the VRF alone doesn't do it.
        route_cmd = ['ip'] if family == 'ipv4' else ['ip', '-6']
        route_cmd += ['route', 'replace']
        vrf = self.config.get('vrf')
        if vrf:
            route_cmd += ['vrf', vrf]
        route_cmd += ['default', 'via', gateway, 'dev', self.ifname]
        if distance:
            route_cmd += ['metric', str(distance)]
        self._cmdl(route_cmd)

    def _remove_bearer_route(self, family):
        route_cmd = ['ip'] if family == 'ipv4' else ['ip', '-6']
        route_cmd += ['route', 'del']
        vrf = self.config.get('vrf')
        if vrf:
            route_cmd += ['vrf', vrf]
        route_cmd += ['default', 'dev', self.ifname]
        try:
            self._cmdl(route_cmd)
        except OSError:
            pass

    def _apply_bearer_dns(self, bearer, family):
        # A current mmcli --output-json reports this as a JSON list under a
        # single 'dns' key rather than the older separate dns1/dns2/dns3
        # keys - fall back to those for an older ModemManager.
        dns = dict_search(f'bearer.{family}-config.dns', bearer)
        if isinstance(dns, list):
            servers = [s for s in dns if s and s != '--']
        else:
            servers = []
            for key in ('dns1', 'dns2', 'dns3'):
                value = dict_search(f'bearer.{family}-config.{key}', bearer)
                if value and value != '--':
                    servers.append(value)
        self._set_hostsd_name_servers(family, servers)

    def _clear_bearer_address(self, family):
        # Skip a static address the operator configured directly - see
        # _apply_bearer_address(). Everything else here was applied by us.
        configured = set(self.config.get('address') or [])
        inet_family = 'inet' if family == 'ipv4' else 'inet6'
        current = get_interface_address(self.ifname) or {}
        for addr_info in current.get('addr_info', []):
            if (
                addr_info.get('family') != inet_family
                or addr_info.get('scope') == 'link'
            ):
                continue
            cidr = f"{addr_info['local']}/{addr_info['prefixlen']}"
            if cidr in configured:
                continue
            if is_intf_addr_assigned(self.ifname, cidr):
                self._cmdl(['ip', 'addr', 'del', cidr, 'dev', self.ifname])
            if cidr in self._addr:
                self._addr.remove(cidr)
        self._set_hostsd_name_servers(family, None)

    def _set_hostsd_name_servers(self, family, servers):
        """servers=None deletes the tag's nameservers without replacing them
        (teardown); servers=[] or a populated list replaces them (apply).
        Uses the same vyos-hostsd tags a real DHCP(v6) client would
        ("dhcp-<ifname>" / "dhcpv6-<ifname>", see 04-vyos-resolvconf and
        dhcp6c-script.j2), not a WWAN-specific one, so an operator's
        `set system name-server <ifname>` trust config works unchanged
        either way."""
        if not is_systemd_service_active('vyos-hostsd'):
            return
        tag = f'dhcp-{self.ifname}' if family == 'ipv4' else f'dhcpv6-{self.ifname}'
        try:
            hc = hostsd_client()
            hc.delete_name_servers([tag])
            if servers:
                hc.add_name_servers({tag: servers})
            hc.apply()
        except VyOSHostsdError:
            pass
