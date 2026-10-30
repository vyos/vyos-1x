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

from vyos.ifconfig.interface import Interface
from vyos.utils.dict import dict_search
from vyos.utils.misc import wait_for
from vyos.utils.network import is_intf_addr_assigned
from vyos.utils.process import cmdl
from vyos.utils.process import is_systemd_service_active
from vyos.utils.wwan import get_bearer_address
from vyos.utils.wwan import get_bearer_router
from vyos.utils.wwan import modem_index
from vyos.utils.wwan import set_bearer_address
from vyos.utils.wwan import set_bearer_router

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
            return result['method'] not in (None, '', '--')

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

    def reapply_bearer(self, config):
        """Re-apply a static bearer's config after the session was re-dialled,
        as the new session can come back with a different address or gateway.
        What the previous session left behind is dropped for a family the new
        one does not supply (yet) or hands to a DHCP(v6) client, and the
        configured DHCP(v6) client or SLAAC is started for it as a commit
        does. Returns True once every configured family is settled, False if
        the settings of one are still missing and the caller should try
        again."""
        self.config = config
        address = config.get('address') or []
        families = []
        if 'dhcp' in address:
            families.append('ipv4')
        if (
            'dhcpv6' in address
            or dict_search('ipv6.address.autoconf', config) is not None
        ):
            families.append('ipv6')
        complete = True
        for family in families:
            bearer, method = self._wait_for_bearer_method(family)
            if method not in (None, '', '--', 'dhcp'):
                if not self._apply_bearer_address(bearer, family):
                    self._forget_bearer(family)
                    complete = False
                continue
            self._forget_bearer(family)
            self._apply_fallback(family)
            if method != 'dhcp':
                complete = False
        return complete

    def del_addr(self, addr: str) -> bool:
        if addr not in ('dhcp', 'dhcpv6'):
            return super().del_addr(addr)

        # Let a real DHCP(v6) client release its lease and clean up its own
        # tag first; only then sweep anything a static bearer applied,
        # since at most one of the two ever had the address.
        result = super().del_addr(addr)
        family = 'ipv4' if addr == 'dhcp' else 'ipv6'
        # Called on every commit where dhcpv6 isn't configured. With autoconf
        # the bearer is owned by set_ipv6_autoconf() and must stay.
        if (
            family == 'ipv6'
            and dict_search('ipv6.address.autoconf', self.config) is not None
        ):
            return result
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

        # A DHCP(v6) client started while the bearer was still missing would
        # keep running next to the settings applied here
        self._stop_address_client(family)

        # A reconnect can negotiate a different address, and there's no
        # config-tree entry for a bearer's address to diff against - remove
        # the one applied from the previous bearer, and only that one.
        previous = get_bearer_address(self.ifname, family)
        if previous and previous != cidr:
            self.del_addr(previous)

        if not is_intf_addr_assigned(self.ifname, cidr):
            tmp = ['ip', 'addr', 'add', cidr, 'dev', self.ifname]
            if family == 'ipv4':
                tmp += ['brd', '+']
            self._cmdl(tmp)
            self._addr.append(cidr)

        set_bearer_address(self.ifname, family, cidr)
        self._set_bearer_router(family, bearer)
        self._apply_bearer_dns(bearer, family)
        return True

    def _apply_fallback(self, family):
        # What a commit does for a family without a static bearer
        if family == 'ipv4':
            super().add_addr('dhcp')
        elif 'dhcpv6' in (self.config.get('address') or []):
            super().add_addr('dhcpv6')
        else:
            super().set_ipv6_autoconf('1')

    def _forget_bearer(self, family):
        # Only when a static bearer left something behind: the DNS tag is
        # shared with a real DHCP(v6) client, whose servers are not ours to drop
        if get_bearer_address(self.ifname, family) or get_bearer_router(
            self.ifname, family
        ):
            self._clear_bearer_address(family)

    def _set_bearer_router(self, family, bearer):
        router = (
            dict_search(f'bearer.{family}-config.gateway', bearer) if bearer else None
        )
        router = None if router == '--' else router
        if router == get_bearer_router(self.ifname, family):
            return None
        set_bearer_router(self.ifname, family, router)
        # The default route is rendered from the gateway, so FRR is reconciled
        # the way a DHCP lease event does it. Not every caller is a commit
        # with a render of its own at the end, e.g. op-mode reconnect.
        try:
            cmdl(
                [
                    'systemd-run',
                    '--no-block',
                    '--collect',
                    '--quiet',
                    '/usr/libexec/vyos/vyos-frr-render.py',
                    '--after-commit',
                ]
            )
        except OSError:
            pass

    def _stop_address_client(self, family):
        if family == 'ipv4':
            unit = f'dhclient@{self.ifname}.service'
        elif dict_search('dhcpv6_options.pd', self.config):
            # DHCPv6-PD is requested through the same client and stays
            return None
        else:
            unit = f'dhcp6c@{self.ifname}.service'

        # A client which cannot get a lease keeps restarting and is never
        # "active", which stop_systemd_unit() would leave alone
        state = cmdl(['systemctl', 'show', '--value', '-p', 'ActiveState', unit])
        if state not in ('active', 'activating', 'reloading'):
            return None
        try:
            cmdl(['systemctl', 'stop', unit])
        except OSError:
            pass
        if family == 'ipv4':
            self.set_dhcp(False)
        else:
            self.set_dhcpv6(False)

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
        cidr = get_bearer_address(self.ifname, family)
        if cidr:
            if is_intf_addr_assigned(self.ifname, cidr):
                self._cmdl(['ip', 'addr', 'del', cidr, 'dev', self.ifname])
            if cidr in self._addr:
                self._addr.remove(cidr)
            set_bearer_address(self.ifname, family, None)
        self._set_bearer_router(family, None)
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
        # Imported here as it pulls in zmq, which no other ifconfig class needs
        from vyos.hostsd_client import Client as hostsd_client
        from vyos.hostsd_client import VyOSHostsdError

        tag = f'dhcp-{self.ifname}' if family == 'ipv4' else f'dhcpv6-{self.ifname}'
        try:
            hc = hostsd_client()
            hc.delete_name_servers([tag])
            if servers:
                hc.add_name_servers({tag: servers})
            hc.apply()
        except VyOSHostsdError:
            pass
