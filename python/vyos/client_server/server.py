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
import contextvars
import dbm
import functools
import logging
import os
import shelve
import signal
import socket
import sys

import attr
import setproctitle
import trio
import voluptuous.humanize

from ..version import get_version
from . import InternalError, Malformed, Protocol, RequestError, STATE_STORE_NAME
from . import trio_except
from .utils import socket_argument_type

trio_except.monkey_patch()


SERVER_VAR = contextvars.ContextVar("SERVER")


class _ConnectionClosed(Exception):
    """
    Indicates that the remote has closed the connection orderly, but while data
    was awaited.
    """


@attr.s(eq=False, repr=False)
class Server:
    """
    A base class for creating server implementations.

    See :mod:`vyos.client_server.client` for the client side.

    In order to create a real server implementation, subclass this and configure
    the behaviour of your new server::

        from vyos.client_server import Protocol
        from vyos.client_server.server import Server

        import voluptuous as vol

        # This must be common between client and server, so better place it in __init__
        MY_PROTOCOL = Protocol(name="my:1")

        class MyServer(Server):
            protocol = MY_PROTOCOL

    Now, implement some actions to be called by clients. Each action must be
    implemented as an async method named ``"action_"`` + the name of the action.

    An action method gets called with the following keyword arguments:

        * ``params``: a dict of the parameters passed by the client
        * ``recv``: an async callable that, when called, waits for a subsequent
          in-request message from the client and returns it
        * ``send``: an async callable which, when passed a dict, sends this as an
          in-request message to the client

    The return value of an action method is sent back to the client as final request
    result.

    If the action method raises an exception, the following happens:

        * If it's not a :exc:`RequestError`, the exception message is taken and
          wrapped into an :exc:`InternalError`, a subtype of :class:`RequestError`
        * A :exc:`RequestError` (or one of its subtypes) is transferred to and
          reraised at the client

    Here are some examples for action implementations::

        async def action_echo(self, params, **kwargs):
            return params

        # Validate parameters passed by client before executing this action
        @validate_params(
            {
                vol.Required("x"): vol.Any(float, int),
                vol.Required("y"): vol.Any(float, int),
            },
        )
        async def action_add(self, params, **kwargs):
            return params["x"] + params["y"]

    Please see the possible class attributes you can set in order to customize the
    server's behavior. These are described below in the comments.

    A working reference client/server implementation can be found under
    :mod:`vyos.ipsetd`.
    """

    #
    # Settings for subclasses
    #

    # Must be an instance of vyos.client_server.Protocol
    protocol = None

    # If a message is larger than this number of bytes, only the names of
    # included fields are logged and values are omitted
    msg_log_values_size_threshold = 1024

    # When True, a path for storing some kind of state persistently can be given
    # and a shelve.Shelf is then opened at that path for the server to use
    supports_state_store = False
    # If True, the state store is mandatory and server won't start without a path
    requires_state_store = False

    cli_default_log_level = "info"
    # Default directory for storing the shelf; None disables state storage by default
    cli_default_state_store_path = "."
    # A string shown at the top of the --help output
    cli_description = None
    cli_stop_signals = (signal.SIGINT, signal.SIGTERM)

    #
    # Arguments
    #

    socket_info = attr.ib(default=None)
    max_connections = attr.ib(converter=int, default=-1)
    socket_timeout = attr.ib(converter=float, default=120.0)
    logger = attr.ib(default=None)
    # A shelve for storing persistent data
    state_store_path = attr.ib(
        default=None, validator=attr.validators.instance_of((str, type(None)))
    )
    state_store = attr.ib(default=None, init=False)
    # Number of accepted connections
    _accepted_num = attr.ib(default=0, init=False)
    # Holds the sockets of connected clients
    _clients = attr.ib(factory=set, init=False)
    # Unparked whenever a client disconnects; used for enforcing max_connections
    _client_disconnected = attr.ib(factory=trio.lowlevel.ParkingLot, init=False)
    # Internal state flag, used for rejecting illegal operations
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
        if self.requires_state_store and self.state_store_path is None:
            raise ValueError("state_store_path is required")
        if isinstance(self.state_store_path, str):
            self.state_store_path = os.path.abspath(self.state_store_path)
        self.banner = self.protocol.generate_banner()

    def __repr__(self):
        tokens = []
        if self._state == 0:
            tokens.append("uninitialized")
        elif self._state == 1:
            tokens.append("serving")
        elif self._state == 2:
            tokens.append("stopped")
        elif self._state == 3:
            tokens.append("dead")
        return f"<{type(self).__name__} {' '.join(tokens)}>"

    async def _serve_client(self, sock, _hash):
        """Run the request processing loop on a client connection."""

        async def _inreq_recv():
            try:
                return await _recv()["inreq"]
            except KeyError:
                raise Malformed("inreq key missing")

        async def _inreq_send(msg):
            await _send({"inreq": msg})

        async def _recv_nbytes(nbytes):
            nonlocal bytes_in
            data = []
            data_len = 0
            while data_len < nbytes:
                part = await sock.recv(nbytes - data_len)
                if not part:
                    raise _ConnectionClosed
                data.append(part)
                part_len = len(part)
                data_len += part_len
                bytes_in += part_len
            return b"".join(data)

        async def _recv():
            async with recv_lock:
                try:
                    msgsize_bytes = await _recv_nbytes(self.protocol.msg_size_len)
                    msgsize = self.protocol.unpack_message_size(msgsize_bytes)
                    try:
                        with trio.fail_after(self.socket_timeout):
                            data = await _recv_nbytes(msgsize)
                    except trio.TooSlowError:
                        # Remote took too long to deliver the announced amount of
                        # data; close the connection
                        raise TimeoutError
                    msg = await trio.to_thread.run_sync(
                        self.protocol.unpack_message, data
                    )
                except ValueError as err:
                    raise Malformed(str(err))
            if msgsize > self.msg_log_values_size_threshold:
                self.logger.debug(
                    "%s.%d: IN: %d, keys=%r", _hash, request_num, msgsize, set(msg)
                )
            else:
                self.logger.debug("%s.%d: IN: %d, %r", _hash, request_num, msgsize, msg)
            return msg

        async def _send(msg):
            data = await trio.to_thread.run_sync(self.protocol.pack_message, msg)
            msgsize = len(data)
            if msgsize > self.msg_log_values_size_threshold:
                self.logger.debug(
                    "%s.%d: OUT: %d, keys=%r", _hash, request_num, msgsize, set(msg)
                )
            else:
                self.logger.debug(
                    "%s.%d: OUT: %d, %r", _hash, request_num, msgsize, msg
                )
            msgsize_bytes = self.protocol.pack_message_size(msgsize)
            try:
                with trio.fail_after(self.socket_timeout):
                    await _sendall(msgsize_bytes)
                    await _sendall(data)
            except trio.TooSlowError:
                # Send operation took too long, close the connection
                raise TimeoutError

        async def _sendall(data):
            """Behavior of ``socket.socket.sendall``, which trio doesn't offer."""
            nonlocal bytes_out
            sent = 0
            nbytes = len(data)
            async with send_lock:
                try:
                    while sent < nbytes:
                        sent += await sock.send(data[sent:] if sent else data)
                finally:
                    bytes_out += sent

        # Serialize calls of _recv() and _sendall()
        recv_lock = trio.Lock()
        send_lock = trio.Lock()

        # ID for differentiating subsequent requests on same connection in logs;
        # incremented whenever a new request is started on this connection
        request_num = 0

        cancelled = False
        try:
            bytes_in_total = 0
            bytes_out_total = 0
            start_time_total = trio.current_time()
            bytes_in = 0
            bytes_out = 0

            # Greet the client
            await _sendall(self.banner)

            while True:
                request_num += 1
                bytes_in = 0
                bytes_out = 0
                start_time = trio.current_time()

                req = None
                try:
                    # Wait for initial request
                    req = await _recv()

                    self.logger.debug("%s.%d: START", _hash, request_num)

                    action = req.get("action")
                    if not isinstance(action, str):
                        raise Malformed("action (string) required")
                    params = req.get("params", {})
                    if not isinstance(params, dict):
                        raise Malformed("params must be dict")
                    try:
                        handler = getattr(self, f"action_{action}")
                    except AttributeError:
                        raise NoSuchAction(action)

                    try:
                        result = await handler(
                            params=params, recv=_inreq_recv, send=_inreq_send
                        )
                    except (_ConnectionClosed, OSError, RequestError):
                        raise
                    # Convert any other error to an unspecific RequestError
                    except Exception as err:
                        self.logger.exception("%s.%d: EXCEPTION", _hash, request_num)
                        raise InternalError(repr(err))

                    await _send({"result": result})

                except RequestError as err:
                    await _send({"error": (err.code, err.args)})

                finally:
                    bytes_in_total += bytes_in
                    bytes_out_total += bytes_out
                    # Only log the END message when a request was actually started
                    if req is not None:
                        self.logger.debug(
                            "%s.%d: END: in=%d, out=%d, time=%.2fms",
                            _hash,
                            request_num,
                            bytes_in,
                            bytes_out,
                            1000 * (trio.current_time() - start_time),
                        )

        # The nursery may raise a trio.MultiError because multiple exceptions may
        # occur at once, so we have to untangle them
        except BaseException as exc:
            for _exc in trio.MultiError.findall(exc, TimeoutError):
                self.logger.warning("%s: TIMEOUT", _hash)
                exc = trio.MultiError.remove(exc, _exc)
            for _exc in trio.MultiError.findall(exc, OSError):
                self.logger.warning("%s: ERROR: %r", _hash, _exc)
                exc = trio.MultiError.remove(exc, _exc)
            _exc = trio.MultiError.find(exc, _ConnectionClosed)
            if _exc:
                # Connection closed; just log the disconnect in finally branch
                exc = trio.MultiError.remove(exc, _exc)
            if trio.MultiError.find(exc, trio.Cancelled):
                cancelled = True
            trio.MultiError.maybe_reraise(exc)

        finally:
            # Ensure self._clients stays consistent with active sockets
            self._clients.remove(sock)
            sock.close()
            self.logger.debug(
                "%s: DISCONNECT: in=%d, out=%d, time=%.2fms",
                _hash,
                bytes_in_total,
                bytes_out_total,
                1000 * (trio.current_time() - start_time_total),
            )
            # Notify main loop that a new connection can be accepted
            self._client_disconnected.unpark()
            # Don't spam the log with stats after each disconnect while shutting down
            if not cancelled:
                self.logger.debug(
                    "CONNECTIONS: %d/%d", len(self._clients), self.max_connections
                )

    def _require_state_store(self):
        if self.state_store is None:
            raise RuntimeError("No state store opened")

    async def state_del(self, key, sync=False):
        """Delete an entry from persistent state store.

        :param key: key of the entry to be removed
        :type  key: str
        :param sync:
            ``True`` ensures changes are synced to disk immediately; in any case,
            pending changes are written on shutdown
        :type  sync: bool
        :raises KeyError: if key not present
        """
        self._require_state_store()
        self.logger.debug("STATE-DEL: %r", key)
        await trio.to_thread.run_sync(self.state_store.__delitem__, key)
        if sync:
            await trio.to_thread.run_sync(self.state_store.sync)

    async def state_get(self, key):
        """Retrieve an entry from persistent state store.

        :param key: key of the entry to be retrieved
        :type  key: str
        :raises KeyError: if key not present
        :return: stored data
        """
        self._require_state_store()
        return await trio.to_thread.run_sync(self.state_store.__getitem__, key)

    async def state_get_all(self):
        """Retrieve all entries from persistent state store.

        :return: dict of stored keys and data
        :rtype: dict
        """
        self._require_state_store()
        return await trio.to_thread.run_sync(dict, self.state_store)

    async def state_restore(self):
        """Implement this method in a subclass.

        It is called during server startup, after the state store was opened,
        but before the server starts listening for requests.

        It is never called when no state store path was configured.
        """
        pass

    async def state_set(self, key, value, sync=False):
        """Create or update an entry in persistent state store.

        :param key: key of the entry to be created/updated
        :type  key: str
        :param value: data to store
        :type  value: object
        :param sync:
            ``True`` ensures changes are synced to disk immediately; in any case,
            pending changes are written on shutdown
        :type  sync: bool
        """
        self._require_state_store()
        self.logger.debug("STATE-STORE: %r", key)
        await trio.to_thread.run_sync(self.state_store.__setitem__, key, value)
        if sync:
            await trio.to_thread.run_sync(self.state_store.sync)

    async def serve(self, task_status=trio.TASK_STATUS_IGNORED):
        """Entry point for running the server.

        ``task_status.started()`` is called when the server is ready to accept
        connections.

        Wrap this method in a subclass if your server implementation requires
        additional startup/shutdown code or open a nursery if background tasks need
        to be run while the server runs.

        :raises OSError:
            if something goes wrong, most likely with the socket, can happen both
            during setup and in operational phase
        :raises dbm.error: if the state store has invalid format (i.e. corrupted)
        :raises RuntimeError: if called more than once per :class:`Server` instance
        """
        if self._state != 0:
            raise RuntimeError("Can only run once")
        self._state = 1

        reset_token = None
        sock = None
        sock_bound = False
        cancelled = False
        try:
            # Provide the Server instance in a context variable for access from code
            # that has no reference to self available, such as validator functions
            # with the @validate_params decorator
            reset_token = SERVER_VAR.set(self)

            # Open persistent state storage
            if self.state_store_path is not None:
                self.logger.info("STATE-OPEN: %r", self.state_store_path)
                try:
                    await trio.to_thread.run_sync(os.makedirs, self.state_store_path)
                except FileExistsError:
                    pass
                self.state_store = await trio.to_thread.run_sync(
                    shelve.open, os.path.join(self.state_store_path, STATE_STORE_NAME)
                )
                await self.state_restore()

            # Work out socket parameters
            socket_info = self.socket_info
            _type = socket_info["type"]
            if _type in {"tcp", "tcp4", "tcp6"}:
                address = (socket_info["host"], socket_info["port"])
                if _type == "tcp4":
                    family = socket.AF_INET
                elif _type == "tcp6":
                    family = socket.AF_INET6
                else:
                    family = (
                        socket.AF_INET6
                        if ":" in socket_info["host"]
                        else socket.AF_INET
                    )
            elif _type == "unix":
                address = socket_info["path"]
                family = socket.AF_UNIX
            else:
                raise ValueError(f"Invalid socket_info: {socket_info!r}")

            sock = trio.socket.socket(family, socket.SOCK_STREAM)
            # Avoid "Address already in use" when restarted shortly after a failure
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Don't listen on IPv4 when using wildcard address "::" in IPv6-only mode
            if self.socket_info["type"] == "tcp6":
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            self.logger.info("BIND: family=%s, address=%r", family.name, address)
            await sock.bind(address)
            sock_bound = True

            if _type == "unix":
                # Eventually change mode or owner
                if socket_info.get("chmod") is not None:
                    self.logger.debug(
                        "CHMOD: %r, %o", socket_info["path"], socket_info["chmod"]
                    )
                    await trio.to_thread.run_sync(
                        os.chmod, socket_info["path"], socket_info["chmod"]
                    )
                uid = socket_info.get("uid")
                gid = socket_info.get("gid")
                if uid is not None or gid is not None:
                    uid = os.getuid() if uid is None else uid
                    gid = os.getgid() if gid is None else gid
                    self.logger.debug("CHOWN: %r, %d:%d", socket_info["path"], uid, gid)
                    await trio.to_thread.run_sync(
                        os.chown, socket_info["path"], uid, gid
                    )

            self.logger.info("LISTEN")
            sock.listen()
            async with trio.open_nursery() as nursery:
                task_status.started()
                while True:
                    # Maybe wait for a free connection slot before accepting
                    if (
                        self.max_connections > -1
                        and len(self._clients) >= self.max_connections
                    ):
                        self.logger.warning(
                            "Maximum of %d concurrent connections reached",
                            self.max_connections,
                        )
                        # Wait for some client to disconnect
                        await self._client_disconnected.park()

                    # Wait for a new client to connect
                    client_sock, client_addr = await sock.accept()
                    # Should improve latency of interactive commands
                    if _type.startswith("tcp"):
                        client_sock.setsockopt(
                            socket.IPPROTO_TCP, socket.TCP_NODELAY, 1
                        )
                    # Start a new processor task for this client
                    self._accepted_num += 1
                    _hash = f"#{self._accepted_num}"
                    self._clients.add(client_sock)
                    self.logger.debug("%s: CONNECT: remote=%r", _hash, client_addr)
                    self.logger.debug(
                        "CONNECTIONS: %d/%d", len(self._clients), self.max_connections
                    )
                    nursery.start_soon(self._serve_client, client_sock, _hash)

        except BaseException as exc:
            for _exc in trio.MultiError.findall(exc, Exception):
                # Mark as died
                self._state = 3
                # Re-raise as the final exception
                raise _exc
            if trio.MultiError.find(exc, trio.Cancelled):
                cancelled = True
            raise exc

        finally:
            if sock is not None:
                sock.close()
            # Remove an eventual stale UNIX socket file
            if sock_bound and socket_info["type"] == "unix":
                self.logger.debug("UNLINK: %r", socket_info["path"])
                with trio.CancelScope(shield=True):
                    try:
                        await trio.to_thread.run_sync(os.unlink, socket_info["path"])
                    except FileNotFoundError:
                        pass
            if self.state_store is not None:
                self.logger.info("STATE-CLOSE")
                with trio.CancelScope(shield=True):
                    await trio.to_thread.run_sync(self.state_store.close)
            if cancelled:
                # Mark as orderly stopped
                self._state = 2
                self.logger.info("STOPPED")
            if reset_token is not None:
                SERVER_VAR.reset(reset_token)

    @property
    def num_connections(self):
        """Number of connected clients."""
        return len(self._clients)

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
            "-C",
            "--max-connections",
            type=int,
            default=-1,
            help="max number of concurrent client connections, default is unlimited",
        )
        parser.add_argument(
            "-s",
            "--socket",
            type=socket_argument_type,
            default=cls.protocol.default_socket,
            help=(
                "socket to listen on for client requests; "
                "either 'tcp[4|6]://<address>:<port>' or "
                "'unix://<path>[,chmod=<xxx>][,chown=<user>][,group=<group>]'; "
            ),
        )
        if cls.supports_state_store:
            parser.add_argument(
                "-S",
                "--state-store-path",
                default=cls.cli_default_state_store_path or "",
                required=cls.requires_state_store
                and cls.cli_default_state_store_path is None,
                help=(
                    "directory for storing/reloading state on startup; "
                    "specify the empty string '' to disable state storage"
                ),
            )
        return parser

    @classmethod
    async def cli_initialize(cls, cli_args: argparse.Namespace, **kwargs) -> "Server":
        """Initialize a :class:`Server` for running from CLI.

        Any extra keyword arguments are passed on to the class's constructor.

        Extend this in your subclass if you need to add additional keyword arguments
        based on the passed CLI arguments.

        :param cli_args: parsed CLI arguments
        """
        kwargs.setdefault("socket_info", cli_args.socket)
        kwargs.setdefault("max_connections", cli_args.max_connections)
        if cls.supports_state_store:
            kwargs.setdefault("state_store_path", cli_args.state_store_path or None)
        return cls(**kwargs)

    @classmethod
    def cli_main(cls, logger: logging.Logger = None) -> int:
        """Entrypoint for running from CLI.

        Register this as a console script entry point, for instance.

        :param logger:
            logger to use for all server-related messages; by default this is the
            one named like the module the server subclass was defined in
        :return: exit code to pass to ``sys.exit``
        """
        if logger is None:
            logger = logging.getLogger(cls.__module__)

        parser = cls.cli_build_argument_parser()
        args = parser.parse_args()

        proctitle = os.path.basename(sys.argv[0])
        setproctitle.setproctitle(proctitle)

        logging.basicConfig(
            format="%(levelname)-8s %(name)s : %(message)s",
            level=args.verbosity.upper(),
        )
        logger.info("%s %s", proctitle, get_version())
        logger.debug("PROTOCOL: %r", cls.protocol)

        async def _main():
            async def _listen_stop_signals():
                with trio.open_signal_receiver(*cls.cli_stop_signals) as sigs:
                    async for sig in sigs:
                        # Convert number to enum variant
                        sig = signal.Signals(sig)
                        logger.info(
                            "Received signal %d (%s), stopping", sig.value, sig.name
                        )
                        nursery.cancel_scope.cancel()

            async with trio.open_nursery() as nursery:
                if cls.cli_stop_signals:
                    nursery.start_soon(_listen_stop_signals)
                server = await cls.cli_initialize(args, logger=logger)
                try:
                    await server.serve()
                # They made dbm.error a tuple, actually...
                except (OSError, *dbm.error) as err:
                    logger.critical("FAILED: %s", err)
                    return 1
                finally:
                    nursery.cancel_scope.cancel()

            return 0

        return trio.run(_main)


async def validate_data(data: T.Any, schema: T.Any) -> T.Any:
    """Validate data using the given schema and raise an exception on failure.

    A :exc:`Malformed` will be raised at the client when he passes invalid data.

    :param data: data to validate
    :param schema:
        a voluptuous schema or the value to pass to the :class:`voluptuous.Schema`
        constructor in order to generate the schema
    :return: validated data
    :raises Malformed: if validation fails
    """
    if not isinstance(schema, voluptuous.Schema):
        schema = voluptuous.Schema(schema)
    try:
        return await trio.to_thread.run_sync(
            # Preserve SERVER_VAR
            contextvars.copy_context().run,
            voluptuous.humanize.validate_with_humanized_errors,
            data,
            schema,
        )
    except voluptuous.Error as err:
        raise Malformed(str(err))


def validate_params(
    schema: T.Union[dict, voluptuous.Schema], handler: T.Callable = None
) -> T.Callable:
    """Decorator for ``action_*()`` methods that performs parameter validation.

    A :exc:`Malformed` will be raised at the client when he passes invalid data.

    :param schema: a dict-based voluptuous schema or dict (will be converted)
    """
    if not isinstance(schema, voluptuous.Schema):
        schema = voluptuous.Schema(schema)
    if handler is None:
        return functools.partial(validate_params, schema)

    async def _validate_params_wrapper(self, params, **kwargs):
        params = await validate_data(params, schema)
        return await handler(self, params=params, **kwargs)

    return _validate_params_wrapper
