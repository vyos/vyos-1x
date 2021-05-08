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

import argparse
import grp
import ipaddress
import pwd
import re


# Regular expressions for validating command line arguments
_IPV4_BLOCK = r"(?:\d{1,2}|[0-1]\d{2}|[0-2][0-5][0-5])"
_IPV4_ADDRESS = fr"{_IPV4_BLOCK}\.{_IPV4_BLOCK}\.{_IPV4_BLOCK}\.{_IPV4_BLOCK}"
_IPV6_ADDRESS = r"(?:[a-f0-9]{,4})?:(?:[a-f0-9]{,4}:){,6}:?(?:[a-f0-9]{,4})?"
_HOST = r"(?:[A-Z0-9_-]+\.)*(?:[A-Z0-9_-]+)"
_PORT = (
    r"(?:\d{1,4}|"
    r"[0-5]\d{4}|"
    r"[0-6][0-4]\d{3}|"
    r"[0-6][0-5][0-4]\d{2}|"
    r"[0-6][0-5][0-5][0-2]\d|"
    r"[0-6][0-5][0-5][0-3][0-5])"
)
_TCP_SOCKET_PATTERN = re.compile(
    r"(?P<proto>tcp[46]?)://"
    fr"(?P<host>{_HOST}|{_IPV4_ADDRESS}|\[{_IPV6_ADDRESS}\])"
    fr":(?P<port>{_PORT})",
    re.I,
)
_UNIX_SOCKET_PATTERN = re.compile(
    r"unix://(?P<path>[^,]+)"
    r"(?:,chmod=(?P<chmod>[0-7]{,3}))?"
    r"(?:,chown=(?P<chown>[a-z0-9_-]+))?"
    r"(?:,chgrp=(?P<chgrp>[a-z0-9_-]+))?",
    re.I,
)


def socket_argument_type(raw_value, allow_hostname=False):
    """Validate a socket specification given at command line."""
    match = _TCP_SOCKET_PATTERN.fullmatch(raw_value)
    if match:
        opts = match.groupdict()
        proto = opts["proto"].lower()
        # Remove the square brackets around IPv6 addresses
        host = opts["host"].lstrip("[").rstrip("]")
        if not allow_hostname:
            try:
                if proto == "tcp4":
                    ipaddress.IPv4Address(host)
                elif proto == "tcp6":
                    ipaddress.IPv6Address(host)
                else:
                    # Let ipaddress module find out the address family
                    ipaddress.ip_address(host)
            except ValueError as err:
                raise argparse.ArgumentTypeError(str(err))
        return {
            "type": proto,
            "host": host,
            "port": int(opts["port"]),
            "uri": f"{proto}://{opts['host']}:{opts['port']}",
        }

    match = _UNIX_SOCKET_PATTERN.fullmatch(raw_value)
    if match:
        opts = match.groupdict()
        uid = None
        if opts["chown"]:
            try:
                uid = int(opts["chown"])
                if uid < 0:
                    raise ValueError
            except ValueError:
                try:
                    uid = pwd.getpwnam(opts["chown"]).pw_uid
                except KeyError:
                    raise argparse.ArgumentTypeError(f"No such user {opts['chown']!r}")
        gid = None
        if opts["chgrp"]:
            try:
                gid = int(opts["chgrp"])
                if gid < 0:
                    raise ValueError
            except ValueError:
                try:
                    gid = grp.getgrnam(opts["chgrp"]).gr_gid
                except KeyError:
                    raise argparse.ArgumentTypeError(f"No such group {opts['chgrp']!r}")
        return {
            "type": "unix",
            "path": opts["path"],
            "chmod": 0o775 if opts["chmod"] is None else int(opts["chmod"], 8),
            "uid": uid,
            "gid": gid,
            "uri": f"unix://{opts['path']}",
        }

    raise argparse.ArgumentTypeError(
        "Valid values are:\n"
        "- tcp[4|6]://<address>:<port>\n"
        "- unix://<path>[,chmod=<xxx>][,chown=<user>][,chgrp=<group>]"
    )
