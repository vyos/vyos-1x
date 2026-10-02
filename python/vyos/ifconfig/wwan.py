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
from time import sleep

from vyos.hostsd_client import Client as hostsd_client
from vyos.hostsd_client import VyOSHostsdError
from vyos.ifconfig.interface import Interface
from vyos.utils.dict import dict_search
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
        # The kernel rejects a default route via the bearer's gateway until
        # the interface is administratively up, which super().update() only
        # does as its last step - so add_addr(), called partway through it,
        # can't install the route directly. Record it here instead and apply
        # it after super().update() returns, same as sibling PPPoEIf does.
        self._pending_bearer_routes = {}
        super().update(config)
        for family, (gateway, distance) in self._pending_bearer_routes.items():
            self._install_bearer_route(family, gateway, distance)
        # A later direct add_addr() call outside of update() (e.g.
        # interactively) must install its route immediately rather than
        # queuing it here with nothing left to flush it.
        del self._pending_bearer_routes

    def _get_active_bearer(self):
        """Return the mmcli --output-json dict for this interface's
        currently connected ModemManager bearer, or None if it doesn't have
        one. A modem can hold a disconnected bearer left over from an
        earlier dial attempt alongside the current one, so this matches on
        status.connected rather than assuming bearers[0] is it."""
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

    def add_addr(self, addr: str, vrf_changed: bool = False) -> bool:
        if addr not in ('dhcp', 'dhcpv6'):
            return super().add_addr(addr, vrf_changed=vrf_changed)

        family = 'ipv4' if addr == 'dhcp' else 'ipv6'

        # A bearer can report itself "connected" slightly before its own
        # ipv4-config/ipv6-config properties are fully populated over D-Bus -
        # retry briefly rather than mistaking that propagation delay for "no
        # static config, start a DHCP(v6) client instead".
        bearer, method = None, None
        for _ in range(10):
            bearer = self._get_active_bearer()
            method = (
                dict_search(f'bearer.{family}-config.method', bearer)
                if bearer
                else None
            )
            if method is not None:
                break
            sleep(0.5)

        if method in (None, '', '--', 'dhcp'):
            if method != 'dhcp':
                # The bearer is missing entirely (lost, or not up yet) -
                # DNS a previous static bearer registered under this
                # family's tag is now stale, and nothing else will clear
                # it: the real DHCP(v6) client this falls through to only
                # replaces the tag on a successful lease, which for a modem
                # that needs this fallback at all may never happen. A
                # bearer whose own method already reports 'dhcp' never had
                # its DNS set this way in the first place, so there's
                # nothing of ours to clear there.
                self._set_hostsd_name_servers(family, None)
            # No active bearer yet, or the network itself wants a real
            # DHCP(v6) exchange for this family (e.g. some ECM/NCM/RNDIS
            # modems) - unchanged, existing behaviour.
            return super().add_addr(addr, vrf_changed=vrf_changed)

        # Anything else (normally "static", the common case for modern QMI
        # raw-ip modems) is applied directly from the bearer's own
        # already-negotiated address/gateway/DNS - a DHCP(v6) client would
        # never get a reply from a static bearer's gateway, just hang or
        # silently do nothing while the interface looks configured.
        return self._apply_bearer_address(bearer, family)

    def set_ipv6_autoconf(self, autoconf):
        if autoconf == '0':
            result = super().set_ipv6_autoconf(autoconf)
            # The base class calls this with '0' on every commit where
            # autoconf isn't configured, not just on a real disable
            # transition, so only sweep if dhcpv6 isn't configured either -
            # otherwise this would delete the address dhcpv6 just applied.
            # dhcpv6 owns its own cleanup via del_addr() when it stops being
            # configured.
            if 'dhcpv6' not in (self.config.get('address') or []):
                self._clear_bearer_address('ipv6')
            return result

        # Same reasoning as add_addr()'s dhcp/dhcpv6 handling: a modem that
        # resolves IPv6 itself over the air never sends RA traffic the
        # kernel's own autoconf could use, so apply the bearer's
        # already-resolved config directly. A modem that genuinely needs
        # host-side SLAAC (e.g. Intel XMM-based) falls through unchanged.
        bearer, method = None, None
        for _ in range(10):
            bearer = self._get_active_bearer()
            method = (
                dict_search('bearer.ipv6-config.method', bearer) if bearer else None
            )
            if method is not None:
                break
            sleep(0.5)

        if method in (None, '', '--', 'dhcp'):
            if method != 'dhcp':
                # Same reasoning as add_addr()'s fallback: a previous static
                # bearer's DNS under this family's tag is now stale, and the
                # real kernel SLAAC this falls through to doesn't use that
                # tag at all, so nothing would ever clear it otherwise.
                self._set_hostsd_name_servers('ipv6', None)
            return super().set_ipv6_autoconf(autoconf)

        return self._apply_bearer_address(bearer, 'ipv6')

    def del_addr(self, addr: str) -> bool:
        if addr not in ('dhcp', 'dhcpv6'):
            return super().del_addr(addr)

        # Let a real DHCP(v6) client (if one is actually running for this
        # family) release its lease and clean up its own vyos-hostsd tag
        # first, exactly as it always has. Only afterwards sweep anything
        # a static bearer applied directly for this family - by
        # construction at most one of the two ever put an address on the
        # interface, so this is never removing something still in use.
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

        # flush_addrs() below removes the addresses themselves regardless of
        # how they got there, but it stops a real DHCP(v6) client via
        # set_dhcp()/set_dhcpv6() directly rather than going through
        # del_addr(), so it never runs the vyos-hostsd tag cleanup a static
        # bearer's DNS servers need - do that here instead.
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

        # A reconnect can negotiate a different address than before, and
        # unlike every other interface type a bearer's address is never
        # recorded in the config tree to diff against - remove whatever of
        # this family is already there except a plain static address the
        # operator explicitly configured on this same leaf-list, which is
        # never ours to touch, so a stale one never ends up coexisting
        # alongside the new one.
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
        # IPv6 has no equivalent 'no-default-route'/'default-route-distance'
        # leaf in this interface's schema (dhcpv6-options.xml.i has neither -
        # unsurprising, since IPv6 default routes normally come from RA, not
        # DHCPv6), so those only ever apply to the IPv4 default route below.
        no_default_route = (
            family == 'ipv4'
            and dict_search('dhcp_options.no_default_route', self.config) is not None
        )
        if not gateway or no_default_route:
            # Withdraw a route a previous commit may have installed, if this
            # one no longer wants one - a bearer's gateway is never recorded
            # in the config tree, so nothing else would notice and remove
            # it. Best-effort: harmless if there's nothing there to remove.
            self._remove_bearer_route(family)
            return

        distance = None
        if family == 'ipv4':
            distance = dict_search('dhcp_options.default_route_distance', self.config)
        if not hasattr(self, '_pending_bearer_routes'):
            # add_addr() can be called directly outside of update() (e.g.
            # interactively) - install immediately rather than queuing with
            # nothing left to flush it.
            self._install_bearer_route(family, gateway, distance)
            return
        self._pending_bearer_routes[family] = (gateway, distance)

    def _install_bearer_route(self, family, gateway, distance):
        # Confirmed live: a device being enslaved to a VRF is not enough on
        # its own for "ip route replace ... dev <if>" to land in that VRF's
        # table rather than main - the vrf keyword has to be given to the
        # route subcommand itself, after "route replace", not before it.
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
        # Skip a plain static address the operator explicitly configured on
        # this same leaf-list - see _apply_bearer_address()'s own comment.
        # Everything else of this family present here was applied by us.
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
