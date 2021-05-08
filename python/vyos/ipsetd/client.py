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

import base64
import hashlib

from ..client_server.client import Client
from . import IPSETD_PROTOCOL, IpsetExistsInServer, NoSuchIpset


# Settings for ipsets created by hostname_to_ipset()
HOSTNAME_IPSET_HASHSIZE = 128
HOSTNAME_IPSET_MAXELEM = 128


class IpsetClient(Client):
    """
    Client for :class:`vyos.ipsetd.server.Server`.

    Use like so::

        with IpsetClient() as client:
            client.create("foo", type="hash:net", family="inet6", takeover=True)
            client.update("foo", set_static=("10.0.0.2", "10.4.5.6"), hostnames={"google.de": False})
            print(c.dump("foo", fields=("static", "hostnames")))
            c.delete("foo")
    """

    protocol = IPSETD_PROTOCOL

    def create(self, name, **params):
        """Create a new ipset in server and kernel.

        :param name: name of ipset to create
        :type  name: str
        :param type: one of ``"hash:ip"``, ``"hash:net"`` (default)
        :type  type: str
        :param family: one of ``"inet"`` (default), ``"inet6"``
        :type  family: str
        :param hashsize: hash size to use (default: 1024)
        :type  hashsize: int
        :param maxelem: max number of entries (default: 65536)
        :type  maxelem: int
        :param refresh_interval:
            how often (in seconds) to re-resolve hostnames (default: 300.0);
            note that a random offset (+/- 10%) is applied after each re-resolving
            to reduce DNS load
        :type  refresh_interval: float, int
        :param tag:
            custom tag to annotate the ipset with (default: "");
            note that the tag is server-internal only and not reflected to kernel
        :type  tag: str
        :param takeover:
            if an ipset with same name already exists in kernel and this is set to
            ``True``, the ipset will be added to server anyways and the existing
            entries in kernel are replaced at next update (default: ``False``)
        :type  takeover: bool
        :raises IpsetExistsInServer: if ipset with same name already exists in server
        :raises IpsetExistsInKernel:
            if ipset with given name already exists in kernel but not in server and
            ``takeover=False``
        :raises IncompatibleIpsetTypes:
            if trying to take over an ipset already present in kernel
            (``takeover=True``), but type/family of existing and created ipset
            don't match
        """
        self.simple_request("create", name=name, **params)

    def delete(self, name):
        """Delete an ipset from server and kernel.

        :param name: name of ipset to delete
        :type  name: str
        :raises NoSuchIpset: if ipset with given name doesn't exist in server
        """
        self.simple_request("delete", name=name)

    def delete_by_tag(self, tag):
        """Delete all ipsets with given tag from server and kernel.

        :param tag: tag of ipsets to delete
        :type  tag: str
        :return: number of ipsets deleted
        :rtype: int
        """
        return self.simple_request("delete_by_tag", tag=tag)

    def dump(self, name, fields=None):
        """Dump properties of an ipset present in server.

        :param name: name of ipset to dump
        :type  name: str
        :param fields:
            if given, dump only these fields; options are: type, family, hashsize,
            maxelem, refresh_interval, tag, static, hostnames
        :type  fields: tuple
        :return: dict of ipset properties
        :rtype: dict
        :raises NoSuchIpset: if ipset with given name doesn't exist in server
        """
        params = {}
        if fields is not None:
            params["fields"] = fields
        return self.simple_request("dump", name=name, **params)

    def hostname_to_ipset(
        self,
        hostname,
        family="inet",
        hashsize=HOSTNAME_IPSET_HASHSIZE,
        maxelem=HOSTNAME_IPSET_MAXELEM,
        refresh_interval=300.0,
        tag="",
        allow_noname=False,
    ):
        """Create an ipset that contains only the given hostname.

        See :meth:`hostname_to_ipset_name` for more details about how the used ipset
        name is calculated.

        If an ipset already exists for the combination of hostname, family and tag,
        only a refresh of the resolved addresses is triggered.

        :param hostname: hostname whose addresses the ipset should contain
        :type  hostname: str
        :param allow_noname:
            whether the previous addresses should be removed when resolving returns
            EAI_NONAME (``True``) or the last known addresses should be used until
            resolving yields results again (``False``)
        :type  allow_noname: bool
        :return: name of the ipset (same as returned by :meth:`hostname_to_ipset_name`)
        :rtype: str

        For the remaining parameters, see :meth:`create`.
        """
        name = self.hostname_to_ipset_name(hostname, family, tag)
        try:
            self.create(
                name,
                type="hash:ip",
                family=family,
                hashsize=hashsize,
                maxelem=maxelem,
                refresh_interval=refresh_interval,
                tag=tag,
                takeover=True,
            )
        except IpsetExistsInServer:
            pass
        self.update(name, set_hostnames={hostname: allow_noname})
        return name

    @staticmethod
    def hostname_to_ipset_name(hostname, family="inet", tag=""):
        """Get the name of the ipset created by :meth:`create_hostname_ipset`.

        The returned ipset name contains a hash suffix created from hostname + tag, so
        the same hostname registered under different tags won't cause a name collision.

        This method works offline, even without instantiating :class:`IpsetClient`,
        so it's very cheap to call, e.g. from templates.

        The parameters have the same meaning as for :meth:`hostname_to_ipset`.

        :return: name of ipset
        :rtype: str
        """
        hostname = hostname.strip().lower()
        # Max name length is 30 chars
        return (
            ("h4:" if family == "inet" else "h6:")
            + hostname[:10]
            + ":"
            + base64.b64encode(
                hashlib.md5(tag.encode() + b":" + hostname.encode()).digest()
            ).decode()[:16]
        )

    def list(self, tag=None):
        """List names of ipsets present in server.

        :param tag: if given, only ipsets with that tag are listed
        :type  tag: str
        :return: tuple of ipset names
        :rtype: tuple
        """
        params = {}
        if tag is not None:
            params["tag"] = tag
        return self.simple_request("list", **params)

    def update(self, name, **params):
        """Update static items and/or hostnames of an ipset.

        :param name: name of ipset to update
        :type  name: str
        :param add_static: static items to add
        :type  add_static: tuple
        :param del_static: static items to delete
        :type  del_static: tuple
        :param set_static: static items to replace the existing items with
        :type  set_static: tuple
        :param add_hostnames:
            dict of hostnames to add; key is hostname and value a bool telling whether
            to remove previously resolved addresses on an EAI_NONAME (``True``)
            or keep them until resolving yields results again (``False``).
        :type  add_hostnames: dict
        :param del_hostnames: hostnames to delete
        :type  del_hostnames: tuple
        :param refresh:
            whether to refresh hostname addresses immediately (default: ``True``)
        :type  refresh: bool
        """
        self.simple_request("update", name=name, **params)
