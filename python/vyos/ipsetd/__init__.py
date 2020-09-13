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

"""
A server that manages ipsets (creation/updating/deletion) in kernel, with the
ability to add hostnames (or, more precisely, the addresses they resolve to) to
ipsets. Resolved addresses are updated periodically.

See :class:`vyos.ipsetd.client.Client` for documentation of the API.
"""

from ..client_server import Protocol, RequestError


IPSETD_PROTOCOL = Protocol("ipsetd/1", default_socket="unix:///run/vyos-ipsetd/sock")


class IncompatibleIpsetTypes(RequestError):
    """
    Raised when trying to create an ipset which already exists in kernel with
    ``takeover=True``, but the existing ipsets type/family differ from those of the
    ipset to be created.
    """

    code = "incompatible_ipset_types"


class IpsetExistsInKernel(RequestError):
    """
    Raised when trying to create an ipset under a name already taken in kernel,
    but not in server.
    """

    code = "ipset_exists_in_kernel"


class IpsetExistsInServer(RequestError):
    """
    Raised when trying to create an ipset under a name already taken in server.
    """

    code = "ipset_exists_in_server"


class NoSuchIpset(RequestError):
    """
    Raised when trying to delete, dump or update an ipset name which doesn't exist
    in server.
    """

    code = "no_such_ipset"
