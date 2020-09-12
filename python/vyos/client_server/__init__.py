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

import typing as T

import struct

import attr
import msgpack


# Path component appended to the specified state store path when opening the shelf
STATE_STORE_NAME = "state"


def _msgpack_default(obj):
    """Convert unserializable types to suitable alternatives."""
    if isinstance(obj, (frozenset, set)):
        return tuple(obj)
    return obj


@attr.s(eq=False, frozen=True, slots=True)
class Protocol:
    """
    An instance of this class defines some properties of a specific application
    protocol and provides methods for implementing communication between client
    and server.
    """

    # struct format that encodes the message size to a 4 byte integer
    # unsigned long, 4 bytes, theoretical message sizes up to 4294967295 bytes
    _msg_size_format = "<L"
    msg_size_len = struct.calcsize(_msg_size_format)
    msg_size_bound = 256 ** msg_size_len - 1

    # Maximum length of banner sent by server (excluding the trailing \n)
    banner_size_max = 128

    name = attr.ib(converter=str, validator=attr.validators.matches_re(r"^\S+$"))
    default_socket = attr.ib(default="unix:///var/run/some.sock")
    # Support messages up to 10 MiB by default
    msg_size_max = attr.ib(converter=int, default=10 * 1024 ** 2)
    # Internal version flag that must be incremented when the wire format changes;
    # this should be included in repr() but not be changeable
    wire_protocol_version = attr.ib(default=1, init=False)

    def __attrs_post_init__(self) -> None:
        if self.msg_size_max > self.msg_size_bound:
            raise ValueError(
                f"msg_size_max ({self.msg_size_max}) > {self.msg_size_bound}"
            )

    def generate_banner(self) -> bytes:
        """Generate welcome message to be sent to clients."""
        return f"{self.wire_protocol_version} {self.name}\n".encode("ascii")

    def pack_message(self, msg: dict) -> bytes:
        """Encode a message as binary data.

        :raises ValueError: if message contains illegal values
        """
        if not isinstance(msg, dict):
            raise ValueError(f"Message must be dict, not {type(msg).__qualname__}")
        try:
            # use_bin_type=True is required in the old msgpack version in buster
            return msgpack.packb(msg, default=_msgpack_default, use_bin_type=True)
        except ValueError as err:
            raise ValueError(f"Illegal message content: {err}")

    def pack_message_size(self, size: int) -> bytes:
        """Encode a message size as binary data.

        :raises ValueError: when size is of invalid type or out of range
        """
        if not isinstance(size, int):
            raise ValueError(f"Message size must be int, not {type(size).__name__!r}")
        if size < 1 or size > self.msg_size_max:
            raise ValueError(
                f"Message size out of range ({size} vs 1...{self.msg_size_max})"
            )
        try:
            return struct.pack(self._msg_size_format, size)
        except struct.error as err:
            raise ValueError(str(err))

    def unpack_message(self, data: bytes) -> dict:
        """Decode a previously binary-encoded message.

        :raises ValueError: if data is invalid
        """
        try:
            # Deserialize sequences to tuples for better performance
            # raw=False is required in the old msgpack version in buster
            msg = msgpack.unpackb(data, use_list=False, raw=False)
        except ValueError as err:
            raise ValueError(f"Invalid message data: {err}")
        if not isinstance(msg, dict):
            raise ValueError(f"Message must be dict, not {type(msg).__qualname__}")
        return msg

    def unpack_message_size(self, data: bytes) -> int:
        """Decode a previously binary-encoded message size.

        :raises ValueError: when data is of invalid type or decoded size out of range
        """
        try:
            (size,) = struct.unpack(self._msg_size_format, data)
        except struct.error as err:
            raise ValueError(str(err))
        if size < 1 or size > self.msg_size_max:
            raise ValueError(
                f"Message size {size} out of range 1...{self.msg_size_max}"
            )
        return size

    def validate_banner(self, banner_bytes: bytes) -> None:
        """Parse the first line as received from a server.

        :raises Malformed: when the banner is malformed
        :raises ProtocolNameMismatch: if protocol names don't match
        :raises WireProtocolVersionMismatch:
            when local/remote wire protocol versions differ
        """
        try:
            banner = banner_bytes.decode("ascii")
            spl = banner.split()
            if len(spl) < 2:
                raise ValueError
            version = int(spl[0])
            name = spl[1]
        except ValueError:
            raise Malformed("Malformed banner") from None
        if version != self.wire_protocol_version:
            raise WireProtocolVersionMismatch(
                {"local": WIRE_PROTOCOL_VERSION, "remote": version}
            )
        if name != self.name:
            raise ProtocolNameMismatch({"local": self.name, "remote": name})


class RequestError(Exception):
    """
    Subtypes of this exception are raised by the ``action_*`` methods of servers and
    translated into an appropriate response and sent to the client, where they're
    recreated and reraised.
    """

    code = "generic"

    @classmethod
    def find_subtype(cls, code: str) -> T.Optional[type]:
        """Return a subtype whose ``code`` attribute matches or ``None``."""
        for _cls in cls.__subclasses__():
            if _cls.code == code:
                return _cls


class InternalError(RequestError):
    """
    Raised when an unexpected exception occurs. Actually receiving this error at
    the client means something bad happened which should be reported.
    """

    code = "internal"


class Malformed(RequestError):
    """
    Raised when a client's request is not formatted as expected (e.g. illegal wire
    protocol, parameter validation etc.).
    """

    code = "malformed"


class NoSuchAction(RequestError):
    """
    Raised when a client tried to execute an action for which no method exists on
    the server class.
    """

    code = "no_such_action"


class ProtocolNameMismatch(RequestError):
    """
    Raised at the client when trying to connect to a server with different protocol
    name.
    """

    code = "protocol_name_mismatch"


class WireProtocolVersionMismatch(RequestError):
    """
    Raised at the client when trying to connect to a server with different wire
    protocol version.
    """

    code = "wire_protocol_version_mismatch"
