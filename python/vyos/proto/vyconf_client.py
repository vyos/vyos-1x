# Copyright 2025 VyOS maintainers and contributors <maintainers@vyos.io>
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
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

import socket
from dataclasses import asdict

from vyos.proto import vyconf_proto
from vyos.proto import vyconf_pb2

from google.protobuf.json_format import MessageToDict
from google.protobuf.json_format import ParseDict

socket_path = '/var/run/vyconfd.sock'


def send_socket(msg: bytearray) -> bytes:
    data = bytes()
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(socket_path)
    client.sendall(msg)

    data_length = client.recv(4)
    if data_length:
        length = int.from_bytes(data_length)
        data = client.recv(length)

    client.close()

    return data


def request_to_msg(req: vyconf_proto.RequestEnvelope) -> vyconf_pb2.RequestEnvelope:
    # pylint: disable=no-member

    msg = vyconf_pb2.RequestEnvelope()
    msg = ParseDict(asdict(req), msg, ignore_unknown_fields=True)
    return msg


def msg_to_response(msg: vyconf_pb2.Response) -> vyconf_proto.Response:
    # pylint: disable=no-member

    d = MessageToDict(msg, preserving_proto_field_name=True)

    response = vyconf_proto.Response(**d)
    return response


def write_request(req: vyconf_proto.RequestEnvelope) -> bytearray:
    req_msg = request_to_msg(req)
    encoded_data = req_msg.SerializeToString()
    byte_size = req_msg.ByteSize()
    length_bytes = byte_size.to_bytes(4)
    arr = bytearray(length_bytes)
    arr.extend(encoded_data)

    return arr


def read_response(msg: bytes) -> vyconf_proto.Response:
    response_msg = vyconf_pb2.Response()  # pylint: disable=no-member
    response_msg.ParseFromString(msg)
    response = msg_to_response(response_msg)

    return response


def send_request(name, *args, **kwargs):
    func = getattr(vyconf_proto, f'set_request_{name}')
    request_env = func(*args, **kwargs)
    msg = write_request(request_env)
    response_msg = send_socket(msg)
    response = read_response(response_msg)

    return response
