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
import dbm
import json
import os
import shelve
import sys

from . import STATE_STORE_NAME


def _json_default(obj):
    """Convert unserializable types to suitable alternatives."""
    if isinstance(obj, (frozenset, set)):
        return tuple(obj)
    raise TypeError(f"{type(obj).__qualname__!r} is not serializable")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Dump the contents of a persistent state store created by a server "
            "implemented using the vyos.client_server toolkit."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--indent",
        type=int,
        default=2,
        help=(
            "number of spaces for JSON indentation; "
            "-1 produces compact single-line output"
        ),
    )
    parser.add_argument("path", help="directory of the state store")
    args = parser.parse_args()

    path = os.path.join(os.path.abspath(args.path), STATE_STORE_NAME)
    try:
        store = shelve.open(path, "r")
    except dbm.error as err:
        if dbm.whichdb(path) is None:
            print(f"No database found at {path!r}", file=sys.stderr)
        else:
            print(f"Can't open {path!r}: {err}", file=sys.stderr)
        return 1

    try:
        state = dict(store)
    except Exception as err:
        print(f"Can't unpickle: {err!r}", file=sys.stderr)
        return 1

    try:
        json.dump(
            state,
            sys.stdout,
            default=_json_default,
            indent=None if args.indent < 0 else args.indent,
            separators=(",", ":") if args.indent < 0 else None,
        )
    except TypeError as err:
        print(f"Can't serialize: {err}", file=sys.stderr)
        return 1

    return 0
