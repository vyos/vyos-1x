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
        # A default route via a bearer's gateway can only be installed once
        # the interface is administratively up - the kernel rejects it as
        # "Nexthop has invalid gateway" otherwise, confirmed live, even
        # though the gateway is genuinely on-link for the address just
        # assigned. The base Interface.update() deliberately brings the
        # link up only as its very last step (to avoid flapping it while
        # other parameters are being reconfigured), so add_addr() below -
        # called from the middle of that same super().update() - cannot
        # install the route directly. It records what to install here
        # instead, and this runs it only after super().update() returns,
        # i.e. after the interface is actually up. Matches WWANIf's own
        # sibling PPPoEIf, which installs its own default route the same
        # way, after calling super().update() first.
        self._pending_bearer_routes = {}
        super().update(config)
        for family, (gateway, distance) in self._pending_bearer_routes.items():
            route_cmd = ['ip'] if family == 'ipv4' else ['ip', '-6']
            route_cmd += [
                'route',
                'replace',
                'default',
                'via',
                gateway,
                'dev',
                self.ifname,
            ]
            if distance:
                route_cmd += ['metric', str(distance)]
            self._cmdl(route_cmd)

    def _get_active_bearer(self):
        """Return the mmcli --output-json dict for this interface's
        currently active ModemManager bearer, or None if no modem/bearer
        can currently be found for it."""
        modem = modem_index(self.ifname)
        if modem is None:
            return None
        try:
            modem_info = loads(cmdl(['mmcli', '--modem', modem, '--output-json']))
        except (OSError, ValueError):
            return None
        bearers = dict_search('modem.generic.bearers', modem_info) or []
        if not bearers:
            return None
        bearer_id = bearers[0].rsplit('/', 1)[-1]
        try:
            return loads(cmdl(['mmcli', '--bearer', bearer_id, '--output-json']))
        except (OSError, ValueError):
            return None

    def add_addr(self, addr: str, vrf_changed: bool = False) -> bool:
        if addr not in ('dhcp', 'dhcpv6'):
            return super().add_addr(addr, vrf_changed=vrf_changed)

        family = 'ipv4' if addr == 'dhcp' else 'ipv6'

        # A bearer can report itself "connected" slightly before its own
        # ipv4-config/ipv6-config properties are fully populated over D-Bus
        # - confirmed live, reproducible specifically on the very first
        # connect right after ModemManager itself just started (not on a
        # later reconnect, where the same query is immediately correct).
        # A short retry here avoids mistaking that brief propagation delay
        # for "this bearer has no static config for this family, start a
        # DHCP(v6) client instead".
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
            # No active bearer yet, or the network itself wants a real
            # DHCP(v6) exchange for this family (e.g. some ECM/NCM/RNDIS
            # modems) - unchanged, existing behaviour.
            return super().add_addr(addr, vrf_changed=vrf_changed)

        # Anything else (normally "static", the common case for modern QMI
        # raw-ip modems) is applied directly from the bearer's own already-
        # negotiated address/gateway/DNS instead of starting a DHCP(v6)
        # client. Neither udhcpc/dhclient nor a DHCPv6 client ever gets a
        # reply from a static bearer's gateway (confirmed against real
        # hardware, see T9326) - starting one here would just hang, or
        # silently do nothing while the interface looks configured.
        return self._apply_bearer_address(bearer, family)

    def set_ipv6_autoconf(self, autoconf):
        if autoconf == '0':
            result = super().set_ipv6_autoconf(autoconf)
            # The base class calls this with '0' on every commit where
            # autoconf isn't configured, not just on an actual
            # enabled-to-disabled transition - confirmed live (it wiped
            # out a dhcpv6-applied address on every commit, T7487-branch
            # testing). Only sweep here if dhcpv6 isn't also configured:
            # if it is, dhcpv6 owns this address and its own del_addr()
            # already handles cleanup when it stops being configured -
            # by construction at most one of the two ever puts an address
            # on the interface, so this must not step on the other one.
            if 'dhcpv6' not in (self.config.get('address') or []):
                self._clear_bearer_address('ipv6')
            return result

        # Same reasoning as add_addr()'s dhcp/dhcpv6 handling: on a modem
        # that resolves IPv6 itself over the air (confirmed live - no RA
        # traffic ever reaches the kernel), the kernel's own autoconf has
        # nothing to autoconfigure from and would never produce an address.
        # Apply the bearer's already-resolved config directly instead; a
        # modem that genuinely needs host-side SLAAC (e.g. Intel XMM-based
        # modems) falls through to the real mechanism unchanged.
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

        # A reconnect can and does negotiate a different address than the
        # previous bearer had (confirmed live) and, unlike every other
        # interface type, a bearer's address is never recorded anywhere in
        # the config tree to diff against - remove whatever of this family
        # is already on the interface first so a stale address never ends
        # up coexisting alongside the new one.
        inet_family = 'inet' if family == 'ipv4' else 'inet6'
        current = get_interface_address(self.ifname) or {}
        for addr_info in current.get('addr_info', []):
            if (
                addr_info.get('family') != inet_family
                or addr_info.get('scope') == 'link'
            ):
                continue
            old_cidr = f"{addr_info['local']}/{addr_info['prefixlen']}"
            if old_cidr != cidr:
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
        # Only records the route to install - see update()'s own doc
        # comment for why this can't just run ip route directly here.
        gateway = dict_search(f'bearer.{family}-config.gateway', bearer)
        if not gateway:
            return
        # IPv6 has no equivalent 'no-default-route'/'default-route-distance'
        # leaf in this interface's schema (dhcpv6-options.xml.i has neither -
        # unsurprising, since IPv6 default routes normally come from RA, not
        # DHCPv6), so those only ever apply to the IPv4 default route below.
        if (
            family == 'ipv4'
            and dict_search('dhcp_options.no_default_route', self.config) is not None
        ):
            return
        distance = None
        if family == 'ipv4':
            distance = dict_search('dhcp_options.default_route_distance', self.config)
        if not hasattr(self, '_pending_bearer_routes'):
            # add_addr() can be called directly outside of update() (e.g.
            # interactively) - fall back to installing immediately rather
            # than silently dropping the route in that case.
            self._pending_bearer_routes = {}
            route_cmd = ['ip'] if family == 'ipv4' else ['ip', '-6']
            route_cmd += [
                'route',
                'replace',
                'default',
                'via',
                gateway,
                'dev',
                self.ifname,
            ]
            if distance:
                route_cmd += ['metric', str(distance)]
            self._cmdl(route_cmd)
            return
        self._pending_bearer_routes[family] = (gateway, distance)

    def _apply_bearer_dns(self, bearer, family):
        # A current mmcli --output-json reports this as a real JSON list
        # under a single 'dns' key (confirmed live) rather than the
        # separate dns1/dns2/dns3 keys the older -K/-K-style flat output
        # uses - fall back to those too in case an older ModemManager
        # still emits that shape under --output-json.
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
        inet_family = 'inet' if family == 'ipv4' else 'inet6'
        current = get_interface_address(self.ifname) or {}
        for addr_info in current.get('addr_info', []):
            if (
                addr_info.get('family') != inet_family
                or addr_info.get('scope') == 'link'
            ):
                continue
            cidr = f"{addr_info['local']}/{addr_info['prefixlen']}"
            if is_intf_addr_assigned(self.ifname, cidr):
                self._cmdl(['ip', 'addr', 'del', cidr, 'dev', self.ifname])
            if cidr in self._addr:
                self._addr.remove(cidr)
        self._set_hostsd_name_servers(family, None)

    def _set_hostsd_name_servers(self, family, servers):
        """servers=None deletes the tag's nameservers without replacing
        them (teardown); servers=[] or a populated list replaces them
        (apply, with the bearer reporting no DNS servers at all in the
        empty-list case). Registered under the exact same vyos-hostsd tags
        a real DHCP(v6) client would use for this interface
        ("dhcp-<ifname>" / "dhcpv6-<ifname>", see 04-vyos-resolvconf and
        dhcp6c-script.j2) rather than a WWAN-specific tag, so an operator's
        existing `set system name-server <ifname>` trust config - which
        looks for precisely these tag names in system_host-name.py - works
        unchanged whether the network handed out addressing over a real
        DHCP(v6) exchange or a static QMI bearer."""
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
