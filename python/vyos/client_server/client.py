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

import argparse
import concurrent.futures
import contextlib
import logging
import os
import socket
import sys
import threading

import attr
import setproctitle

from ..version import get_version
from . import (
    Malformed,
    Protocol,
    RequestError,
    ProtocolNameMismatch,
    WireProtocolVersionMismatch,
)
from .utils import socket_argument_type


class RequestComplete(Exception):
    """
    Raised by ``recv()`` when it receives a successful request completion message.

    This is an implementation detail and should never propagate out when using the
    API of :class:`Client`.
    """

    def __init__(self, result):
        self.result = result


class RequestIncomplete(Exception):
    """
    Raised by ``request()`` when the context manager was left without receiving
    prior request completion.
    """


@attr.s(eq=False, repr=False)
class Client:
    """
    A base class for creating client implementations.

    See :mod:`vyos.client_server.server` for the server side.

    In order to create a real client implementation, subclass this and configure
    the behaviour of your new client::

        from vyos.client_server import Protocol
        from vyos.client_server.client import Client

        # This must be common between client and server, so better place it in __init__
        MY_PROTOCOL = Protocol(name="my:1")

        class MyClient(Client):
            protocol = MY_PROTOCOL

    Now implement the public API users of your client should work with. Especially,
    see :meth:`request`.

    The final client can then be used like so::

        # The use as a context manager automatically connects/disconnects the socket
        with MyClient() as client:
            print(client.add(40, 2))

    Please see the possible class attributes you can set in order to customize the
    client's behavior. These are described below in the comments.

    A working reference client/server implementation can be found under
    :mod:`vyos.ipsetd`.
    """

    #
    # Settings for subclasses
    #

    # Must be an instance of vyos.client_server.Protocol
    protocol = None

    cli_default_log_level = "warning"
    # A string shown at the top of the --help output
    cli_description = None

    #
    # Arguments
    #

    socket_info = attr.ib(default=None)
    connect_timeout = attr.ib(converter=float, default=10.0)
    socket_timeout = attr.ib(converter=float, default=120.0)
    logger = attr.ib(default=None)
    _lock = attr.ib(factory=threading.Lock, init=False)
    # Holds the socket after connecting
    _sock = attr.ib(default=None, init=False)
    # Holds the address after connecting
    _address = attr.ib(default=None, init=False)
    _state = attr.ib(default=0, init=False)

    def __attrs_post_init__(self):
        if not isinstance(self.protocol, Protocol):
            raise TypeError("protocol class attribute must be an instance of Protocol")
        if self.socket_info is None:
            self.socket_info = self.protocol.default_socket
        if isinstance(self.socket_info, str):
            self.socket_info = socket_argument_type(self.socket_info)
        if self.logger is None:
            self.logger = logging.getLogger(type(self).__module__)

    def __del__(self):
        self.close()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.close()

    def __repr__(self):
        tokens = []
        if self._state == 0:
            tokens.append("initializing")
        elif self._state == 1:
            tokens.extend((self._address, "connected"))
        elif self._state == 2:
            tokens.append("stopped")
        return f"<{type(self).__name__} {' '.join(tokens)}>"

    def _recv(self) -> dict:
        """Receive a message from the server.

        :raises RuntimeError: when called outside a request
        """
        if not self._lock.locked():
            raise RuntimeError("Call to recv() outside of request")
        msgsize_bytes = self._recv_nbytes(self.protocol.msg_size_len)
        try:
            msgsize = self.protocol.unpack_message_size(msgsize_bytes)
        except ValueError as err:
            raise Malformed(str(err))
        data = self._recv_nbytes(msgsize)
        try:
            return self.protocol.unpack_message(data)
        except ValueError as err:
            raise Malformed(str(err))

    def _recv_nbytes(self, nbytes: int) -> bytes:
        """Receive exactly this number of bytes."""
        data = []
        data_len = 0
        while data_len < nbytes:
            part = self._sock.recv(nbytes - data_len)
            if not part:
                # TODO: This is probably not semantically appropriate, but it does
                # the job because a server closing the connection during a request
                # always is a fatal error
                raise ConnectionResetError("Remote hung up unexpectedly")
            data.append(part)
            data_len += len(part)
        return b"".join(data)

    def _send(self, msg: dict) -> None:
        """Send a message to the server.

        :raises RuntimeError: when called outside a request
        """
        if not self._lock.locked():
            raise RuntimeError("Call to send() outside of request")
        data = self.protocol.pack_message(msg)
        msgsize = len(data)
        msgsize_bytes = self.protocol.pack_message_size(msgsize)
        self._sock.sendall(msgsize_bytes)
        self._sock.sendall(data)

    def close(self):
        """Close connection to server, if one is open."""
        with self._lock:
            if self._state == 2:
                return
            if self._state == 1:
                self._sock.close()
            self._state = 2

    def connect(self):
        """Connect to server.

        :raises OSError: if I/O fails
        :raises RuntimeError: if called more than once or after :meth:`close`
        :raises Malformed:
        :raises ProtocolNameMismatch:
        :raises WireProtocolVersionMismatch:
        """
        socket_info = self.socket_info
        with self._lock:
            if self._state != 0:
                raise RuntimeError("Can only connect the client once")
            self.logger.info("CONNECTING")
            _type = socket_info["type"]
            if _type == "tcp":
                # Try both IPv4 and IPv6, return the socket for which connect() succeeded
                sock = socket.create_connection(
                    (socket_info["host"], socket_info["port"]),
                    timeout=self.connect_timeout,
                )
            else:
                if _type == "tcp4":
                    family = socket.AF_INET
                    address = socket_info["host"], socket_info["port"]
                elif _type == "tcp6":
                    family = socket.AF_INET6
                    address = socket_info["host"], socket_info["port"]
                elif _type == "unix":
                    family = socket.AF_UNIX
                    address = socket_info["path"]
                else:
                    raise ValueError(f"Invalid socket_info: {socket_info!r}")
                sock = socket.socket(family, socket.SOCK_STREAM)
                sock.settimeout(self.connect_timeout)
                sock.connect(address)

            # After connecting, switch to the genuine socket timeout
            sock.settimeout(self.socket_timeout)
            # Should improve latency of interactive commands
            if socket_info["type"].startswith("tcp"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._sock = sock
            self._address = sock.getpeername()

            # Parse the welcome message
            chars = []
            while len(chars) <= self.protocol.banner_size_max:
                char = self._recv_nbytes(1)
                if char == b"\n":
                    break
                chars.append(char)
            else:
                raise Malformed(
                    f"Remote banner longer than {self.protocol.banner_size_max}"
                )
            banner_bytes = b"".join(chars)
            self.logger.debug("Remote banner: %r", banner_bytes)
            self.protocol.validate_banner(banner_bytes)

            self._state = 1
            self.logger.info("CONNECTED: %r", self._sock.getpeername())

    def inreq_recv(self) -> dict:
        """Receive an in-request message from the server.

        :raises RuntimeError: when called outside a request
        """
        msg = self._recv()
        try:
            result = msg["result"]
        except KeyError:
            pass
        else:
            # Raise a special exception which is caught by the request() context
            # manager, telling it the request has ended
            raise RequestComplete(result)
        try:
            error_code, error_args = msg["error"]
        except KeyError:
            pass
        else:
            error_type = RequestError.find_subtype(error_code)
            if error_type is None:
                raise Malformed(f"No error type for code {error_code!r}")
            raise error_type(*error_args)
        try:
            return msg["inreq"]
        except KeyError:
            pass
        raise Malformed("Neither result, error nor inreq in message")

    def inreq_send(self, msg: dict) -> None:
        """Send an in-request message to the server.

        :raises RuntimeError: when called outside a request
        """
        self._send({"inreq": msg})

    @contextlib.contextmanager
    def request(
        self, action: str, **params: T.Any
    ) -> contextlib.AbstractContextManager:
        """Execute an action on the server.

        All extra keyword arguments are passed to the action as parameters (``params``
        keyword argument of the server's action method).

        This method returns a context manager which sends the request upon
        entering. While inside the context, :meth:`inreq_recv` and :meth:`inreq_send`
        can be used to send/receive extra in-request dict messages.

        Upon entering, the context manager will return a
        :class:`concurrent.futures.Future` object, which will hold the request's
        final result (that returned by the server's action method) **after** the
        context manager has exited.

        As soon as a request completion is received, :meth:`inreq_recv` will raise
        some special exception which then causes the context manager to be left
        orderly and the result future to be populated.

        However, you don't have to call :meth:`inreq_recv` yourself if the server
        action you're executing requires no in-request communication. For such simple
        cases, better use :meth:`simple_request`.

        :param action: name of the action to call
        :raises OSError: if I/O fails
        :raises RuntimeError: if not connected
        :raises RequestError: if anything goes wrong during the request
        :raises RequestIncomplete:
            when leaving the returned context manager without receiving prior request
            completion from server
        """
        with self._lock:
            if self._state != 1:
                raise RuntimeError(f"{self!r} is not connected")
            req = {"action": action, "params": params}
            self._send(req)
            # This is yielded by the context manager and will be populated with
            # the request's result after it completed successfully and the context
            # block was left
            result = concurrent.futures.Future()
            try:
                # Now there's time to send action-specific in-request messages back
                # and forth
                yield result
            except RequestComplete as err:
                # Server sent a request completion message; end the context manager
                # and populate the yielded Future with the request's result
                result.set_result(err.result)
                self.logger.debug("Request completed: %r", result)
            else:
                raise RequestIncomplete(
                    f"request({action!r}) context manager left without receiving "
                    "prior request completion"
                )

    def simple_request(self, action, **params):
        """An alternative to :meth:`request` that permits no in-request communication.

        Parameters are identical to :meth:`request`, but it directly returns the
        request result, no need to fiddle with futures or anything.

        :return: the request result as returned by the server's action method
        :raises OSError: if I/O fails
        :raises RuntimeError: if not connected
        :raises RequestError: if anything goes wrong during the request
        :raises RequestIncomplete:
            when trying to use this for an action that requires in-request
            communication
        """
        with self.request(action, **params) as result:
            # The server is now expected to send a request completion message
            self.inreq_recv()
            # If the request completed, the context is left already
            raise RequestIncomplete(
                f"Action {action!r} seems to require in-request communication; "
                "use request() instead"
            )
        return result.result()

    #
    # CLI interface
    #

    @classmethod
    def cli_build_argument_parser(cls) -> argparse.ArgumentParser:
        """Build the argparse parser for parsing CLI arguments.

        Extend the returned parser in your own subclass if you need to add more
        arguments.
        """
        parser = argparse.ArgumentParser(
            description=cls.cli_description,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        parser.add_argument(
            "-v",
            "--verbosity",
            choices=("debug", "info", "warning", "error", "critical"),
            default=cls.cli_default_log_level.lower(),
            help="logging verbosity",
        )
        parser.add_argument(
            "-s",
            "--socket",
            type=socket_argument_type,
            default=cls.protocol.default_socket,
            help=(
                "socket of server to connect to; "
                "either 'tcp[4|6]://<address>:<port>' or "
                "'unix://<path>'; "
            ),
        )
        return parser

    @classmethod
    def cli_initialize(cls, cli_args: argparse.Namespace, **kwargs) -> "Client":
        """Initialize a :class:`Client` for running from CLI.

        Any extra keyword arguments are passed on to the class's constructor.

        Extend this in your subclass if you need to add additional keyword arguments
        based on the passed CLI arguments.

        :param cli_args: parsed CLI arguments
        """
        kwargs.setdefault("socket_info", cli_args.socket)
        return cls(**kwargs)

    @classmethod
    def cli_main(cls, logger: logging.Logger = None) -> int:
        """Entrypoint for running from CLI.

        Register this as a console script entry point, for instance.

        :param logger:
            logger to use for all client-related messages; by default this is the
            one named like the module the client subclass was defined in
        :return: exit code to pass to ``sys.exit``
        """
        if logger is None:
            logger = logging.getLogger(cls.__module__)

        parser = cls.cli_build_argument_parser()
        args = parser.parse_args()

        proctitle = os.path.basename(sys.argv[0])
        setproctitle.setproctitle(proctitle)

        logging.basicConfig(
            format="%(levelname)-8s : %(message)s", level=args.verbosity.upper()
        )
        logger.info("%s %s", proctitle, get_version())
        logger.debug("PROTOCOL: %r", cls.protocol)

        client = cls.cli_initialize(args, logger=logger)
        try:
            with client:
                return client.cli_run(args) or 0
        except OSError as err:
            logger.critical("OSError: %s", err)
            return 1
        except RequestError as err:
            logger.critical("Request failed: %s", err)
            return 1
        except KeyboardInterrupt:
            return 1

    def cli_run(self, cli_args: argparse.Namespace) -> int:
        """Implement your client logic in this method.

        By the time this is called, the client is connected already.

        :param cli_args: parsed CLI arguments
        :return: exit code to pass to ``sys.exit``
        """
        raise NotImplementedError("Implement this method in subclass")
