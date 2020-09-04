# Copyright (C) 2020 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import ipaddress
import itertools
import random
import socket
import subprocess

import attr
import trio
import voluptuous as vol

from ..client_server import Malformed
from ..client_server.server import SERVER_VAR, Server, validate_params
from . import (
    IPSETD_PROTOCOL,
    IncompatibleIpsetTypes,
    IpsetExistsInKernel,
    IpsetExistsInServer,
    NoSuchIpset,
)


DUMP_ALL_FIELDS = (
    "type",
    "family",
    "hashsize",
    "maxelem",
    "refresh_interval",
    "tag",
    "static",
    "hostnames",
)


def _update_validate_static(params):
    server = SERVER_VAR.get()
    ipset = server._get_ipset(params["name"])
    # Validate static items depending on ipset type
    for key in ("add_static", "del_static", "set_static"):
        if key in params:
            validated = set()
            for idx, item in enumerate(params[key]):
                try:
                    validated.add(ipset.validate_item(item))
                except ValueError as err:
                    raise vol.Invalid(str(err), path=[key, idx])
            params[key] = validated
    return params


@attr.s(eq=False, slots=True)
class Ipset:
    """
    An object representing an ipset controlled by the server.
    """

    name = attr.ib(
        converter=str,
        # Maximum allowed length is 31 chars, but we reserve 1 for the
        # prefix of temporary ipset names; spaces are forbidden due to
        # escaping issues in restore scripts
        validator=attr.validators.matches_re(r"^[^\s.]\S{0,29}$"),
    )
    type = attr.ib(
        default="hash:net", validator=attr.validators.in_(("hash:ip", "hash:net",))
    )
    family = attr.ib(default="inet", validator=attr.validators.in_(("inet", "inet6")))
    hashsize = attr.ib(converter=int, default=1024)
    maxelem = attr.ib(converter=int, default=65536)
    refresh_interval = attr.ib(converter=float, default=300.0)
    tag = attr.ib(converter=str, default="")
    static = attr.ib(converter=set, factory=set, repr=False)
    hostnames = attr.ib(converter=dict, factory=dict, repr=False)
    state = attr.ib(default=None, init=False, repr=False)
    lock = attr.ib(factory=trio.Lock, init=False, repr=False)
    refresh_event = attr.ib(factory=trio.Event, init=False, repr=False)
    watcher_cancel_scope = attr.ib(factory=trio.CancelScope, init=False, repr=False)

    def __attrs_post_init__(self):
        if self.hashsize < 1:
            raise ValueError(f"hashsize ({self.hashsize}) must be positive")
        if self.maxelem < 1:
            raise ValueError(f"maxelem ({self.maxelem}) must be positive")
        # Refresh at most every 60 seconds
        self.refresh_interval = max(60, self.refresh_interval)

    def dump(self):
        """Return settings as keyword arguments for recreating this ipset."""
        return {
            n: getattr(self, n)
            for n in (
                "type",
                "family",
                "hashsize",
                "maxelem",
                "refresh_interval",
                "tag",
                "static",
                "hostnames",
            )
        }

    def get_create_args(self):
        return (
            self.type,
            "family",
            self.family,
            "hashsize",
            str(self.hashsize),
            "maxelem",
            str(self.maxelem),
        )

    def validate_item(self, item):
        if self.type == "hash:ip":
            if self.family == "inet":
                return str(ipaddress.IPv4Address(item))
            return str(ipaddress.IPv6Address(item))
        if self.family == "inet":
            return str(ipaddress.IPv4Network(item))
        return str(ipaddress.IPv6Network(item))


class IpsetFailed(Exception):
    """
    Raised when the ipset command exits non-zero.
    """


class IpsetServer(Server):
    protocol = IPSETD_PROTOCOL
    supports_state_store = True
    default_state_store_path = "/run/vyos-ipsetd/state"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ipsets = {}

    async def _create_ipset(self, name, store=True, takeover=False, **kwargs):
        """Insert a new controlled ipset into server, kernel and state store."""
        if name in self._ipsets:
            raise IpsetExistsInServer(name)

        ipset = Ipset(name, **kwargs)
        # Will enter immediately without giving another task a chance to run in between
        async with ipset.lock:
            self._ipsets[name] = ipset
            try:
                await self._run_ipset("create", name, *ipset.get_create_args())
            except IpsetFailed as err:
                if not takeover:
                    raise IpsetExistsInKernel(name)
                # Check whether the existing set has same signature as the new one
                try:
                    hdr = await self._parse_ipset_header(name)
                except NoSuchIpset:
                    # Obviously, there was no name clash and something
                    # else went wrong while creating the ipset; reraise
                    # original error
                    raise err
                if ipset.type != hdr["type"] or ipset.family != hdr["family"]:
                    raise IncompatibleIpsetTypes(
                        {"type": ipset.type, "family": ipset.family},
                        {"type": hdr["type"], "family": hdr["family"]},
                    )
                # Ok, headers match; we can take over this ipset
                self.logger.debug("TAKEOVER: %r", name)
            finally:
                # Delete the ipset in case anything went wrong...
                del self._ipsets[name]
            # ... and insert it again if it didn't
            self._ipsets[name] = ipset

        self.logger.info("CREATE: %r", ipset)
        self.nursery.start_soon(self._watch_ipset, ipset)
        if store:
            await self._store_ipset(ipset)
        return ipset

    async def _delete_ipset(self, ipset):
        """Delete ipset from server, kernel and state store."""
        async with ipset.lock:
            if ipset is not self._ipsets.get(ipset.name):
                raise NoSuchIpset(ipset.name)
            self.logger.info("DELETE: %r", ipset.name)
            try:
                await self._run_ipset("destroy", ipset.name)
            except IpsetFailed as err:
                self.logger.warning("DELETE: %r, %r", ipset.name, err)
            ipset.watcher_cancel_scope.cancel()
            if self.state_store is not None:
                try:
                    await self.state_del(ipset.name)
                except KeyError:
                    pass
            del self._ipsets[ipset.name]

    def _get_ipset(self, name):
        """This is to be used in ``action_*()``."""
        try:
            return self._ipsets[name]
        except KeyError:
            raise NoSuchIpset(name) from None

    async def _parse_ipset_header(self, name):
        """Read information about an existing ipset from kernel into a dict."""
        try:
            output = await self._run_ipset("-t", "list", name, stdout=True)
        except IpsetFailed:
            raise NoSuchIpset(name)
        output = output.splitlines()
        _type = output[1].split()[1]
        hdr = output[3].split()[1:]
        return {
            "type": _type,
            "family": hdr[1],
            "hashsize": int(hdr[3]),
            "maxelem": int(hdr[5]),
        }

    async def _refresh_ipset(self, ipset):
        """(Re-)resolve hostnames and rewrite ipset to kernel if necessary."""
        async with ipset.lock:
            all_items = set(ipset.static)
            family = socket.AF_INET if ipset.family == "inet" else socket.AF_INET6
            for hostname, (allow_noname, old_addrs) in ipset.hostnames.items():
                try:
                    addrs = frozenset(
                        info[4][0]
                        for info in await trio.socket.getaddrinfo(hostname, 0, family)
                    )
                except socket.gaierror as err:
                    if allow_noname and err.errno == socket.EAI_NONAME:
                        addrs = frozenset()
                    else:
                        self.logger.warning(
                            "UNRESOLVABLE: %r [%s], %s", hostname, family.name, err
                        )
                        # Reuse previously resolved addresses
                        all_items.update(old_addrs)
                        continue
                self.logger.debug(
                    "RESOLVED: %r [%s] = %r", hostname, family.name, sorted(addrs)
                )
                old_addrs.clear()
                old_addrs.update(addrs)
                all_items.update(addrs)

            # Also causes a rewrite at first run (ipset.state == None)
            if all_items == ipset.state:
                self.logger.debug("UNCHANGED: %r", ipset.name)
                return

            if len(all_items) > ipset.maxelem:
                self.logger.error(
                    "REWRITE: %r, Set too large (items=%d, maxelem=%d)",
                    ipset.name,
                    len(all_items),
                    ipset.maxelem,
                )
                return

            self.logger.info("REWRITE: %r, items=%d", ipset.name, len(all_items))
            tmp_name = f".{ipset.name}"
            try:
                create_args = " ".join(ipset.get_create_args())
                await self._run_ipset(
                    "-!",
                    "restore",
                    stdin="\n".join(
                        itertools.chain(
                            (
                                # Also try to create the original ipset
                                # in case it was deleted in between;
                                # will fail silently if it already exists due to -!
                                f"create {ipset.name} {create_args}",
                                f"create {tmp_name} {create_args}",
                            ),
                            (f"add {tmp_name} {item}" for item in all_items),
                            (f"swap {ipset.name} {tmp_name}", f"destroy {tmp_name}"),
                        )
                    ),
                )
            except IpsetFailed as err:
                # Ensure the tmp ipset gets removed in any case
                try:
                    await self._run_ipset("destroy", tmp_name)
                except IpsetFailed:
                    pass
                self.logger.error("REWRITE: %r, %s", ipset.name, err)
            else:
                ipset.state = all_items
                # Persist the resolved addresses
                await self._store_ipset(ipset)

    async def _run_ipset(self, *args, stdin="", stdout=False):
        try:
            result = await trio.run_process(
                ("ipset", *args),
                stdin=stdin.encode(),
                capture_stdout=stdout,
                capture_stderr=True,
            )
        except subprocess.CalledProcessError as err:
            raise IpsetFailed(err.stderr.decode().strip())
        if stdout:
            return result.stdout.decode().strip()

    async def _store_ipset(self, ipset):
        """Save ipset to persistent state store."""
        if self.state_store is None:
            return
        await self.state_set(ipset.name, ipset.dump())

    async def _watch_ipset(self, ipset):
        """Monitor task that periodically refreshes an ipset."""
        with ipset.watcher_cancel_scope:
            while True:
                # Randomize delay by +/- 10% to spread load on DNS
                delay = (0.9 + 0.2 * random.random()) * ipset.refresh_interval
                with trio.move_on_after(delay):
                    await ipset.refresh_event.wait()
                    ipset.refresh_event = trio.Event()
                await self._refresh_ipset(ipset)

    #
    # Actions follow
    #

    @validate_params(
        {
            vol.Required("name"): str,
            # Real data validation for these is performed by the Ipset constructor later
            vol.Optional("type"): str,
            vol.Optional("family"): str,
            vol.Optional("hashsize"): int,
            vol.Optional("maxelem"): int,
            vol.Optional("refresh_interval"): vol.Any(float, int),
            vol.Optional("tag"): str,
            vol.Optional("takeover"): bool,
        }
    )
    async def action_create(self, params, **kwargs):
        name = params["name"]
        kwargs = {
            k: params[k]
            for k in (
                "type",
                "family",
                "hashsize",
                "maxelem",
                "refresh_interval",
                "tag",
                "takeover",
            )
            if k in params
        }
        kwargs["name"] = name
        kwargs["store"] = True
        try:
            await self._create_ipset(**kwargs)
        except (ValueError, TypeError) as err:
            raise Malformed(str(err))

    @validate_params({vol.Required("name"): str})
    async def action_delete(self, params, **kwargs):
        ipset = self._get_ipset(params["name"])
        try:
            await self._delete_ipset(ipset)
        except NoSuchIpset:
            pass

    @validate_params({vol.Required("tag"): str})
    async def action_delete_by_tag(self, params, **kwargs):
        ipsets = tuple(
            ipset for ipset in self._ipsets.values() if ipset.tag == params["tag"]
        )
        for ipset in ipsets:
            try:
                await self._delete_ipset(ipset)
            except NoSuchIpset:
                pass
        return len(ipsets)

    @validate_params(
        {
            vol.Required("name"): str,
            vol.Optional("fields", default=DUMP_ALL_FIELDS): vol.All(
                DUMP_ALL_FIELDS, vol.Coerce(set)
            ),
        }
    )
    async def action_dump(self, params, **kwargs):
        ipset = self._get_ipset(params["name"])
        fields = params["fields"]
        data = {field: getattr(ipset, field) for field in fields}
        if "hostnames" in data:
            data["hostnames"] = {
                hostname: allow_noname
                for hostname, (allow_noname, _) in data["hostnames"].items()
            }
        return data

    @validate_params({vol.Optional("tag"): str})
    async def action_list(self, params, **kwargs):
        if "tag" in params:
            return tuple(
                name
                for name, ipset in self._ipsets.items()
                if ipset.tag == params["tag"]
            )
        return tuple(self._ipsets)

    @validate_params(
        vol.All(
            {
                vol.Required("name"): str,
                vol.Optional("refresh", default=True): bool,
                # These tuples will be converted to sets by _update_validate_static()
                vol.Optional("add_static"): (str,),
                vol.Optional("del_static"): (str,),
                vol.Optional("set_static"): (str,),
                vol.Optional("add_hostnames"): vol.All(
                    {vol.All(str, str.strip, str.lower): bool}
                ),
                vol.Optional("del_hostnames"): vol.All(
                    (vol.All(str, str.strip, str.lower),), vol.Coerce(set)
                ),
                vol.Optional("set_hostnames"): vol.All(
                    {vol.All(str, str.strip, str.lower): bool}
                ),
            },
            _update_validate_static,
        )
    )
    async def action_update(self, params, **kwargs):
        name = params["name"]
        ipset = self._get_ipset(name)

        async with ipset.lock:
            num_static_before = len(ipset.static)
            try:
                ipset.static = params["set_static"]
            except KeyError:
                try:
                    ipset.static.difference_update(params["del_static"])
                except KeyError:
                    pass
                try:
                    ipset.hostnames.update(params["add_hostnames"])
                except KeyError:
                    pass

            num_hostnames_before = len(ipset.hostnames)
            try:
                ipset.hostnames = {
                    hostname: (allow_noname, set())
                    for hostname, allow_noname in params["set_hostnames"].items()
                }
            except KeyError:
                try:
                    for hostname in params["del_hostnames"]:
                        try:
                            del ipset.hostnames[hostname]
                        except KeyError:
                            pass
                except KeyError:
                    pass
                try:
                    ipset.hostnames.update(
                        (hostname, (allow_noname, set()))
                        for hostname, allow_noname in params["add_hostnames"].items()
                    )
                except KeyError:
                    pass

            self.logger.info(
                "UPDATE: %r, static: %d +%d -%d !%d =%d, "
                "hostnames: %d +%d -%d !%d =%d, %s",
                name,
                num_static_before,
                len(params.get("add_static", ())),
                len(params.get("del_static", ())),
                len(params.get("set_static", ())),
                len(ipset.static),
                num_hostnames_before,
                len(params.get("add_hostnames", ())),
                len(params.get("del_hostnames", ())),
                len(params.get("set_hostnames", ())),
                len(ipset.hostnames),
                "refresh" if params["refresh"] else "no refresh",
            )

        if params["refresh"]:
            ipset.refresh_event.set()
        await self._store_ipset(ipset)

    async def state_restore(self):
        self.logger.info("Restoring ipsets from stored state")
        state = await self.state_get_all()
        for name, kwargs in state.items():
            try:
                ipset = await self._create_ipset(
                    name, store=False, takeover=True, **kwargs
                )
            except IncompatibleIpsetTypes as err:
                self.logger.warning(
                    "Can't restore %r due to existing ipset  with "
                    "incompatible type: %s",
                    name,
                    err,
                )
                continue
            # Trigger initial rewriting
            ipset.refresh_event.set()
        self.logger.info("Restored %d of %d ipset(s)", len(self._ipsets), len(state))

    async def serve(self):
        """Wrapper that opens an additional nursery for background tasks."""
        # Provide a nursery for all the _watch_ipset() tasks
        async with trio.open_nursery() as nursery:
            self.nursery = nursery

            # Run the real server
            await super().serve()
