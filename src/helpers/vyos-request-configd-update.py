#!/usr/bin/env python3

import json
import zmq

from vyos.utils.commit import wait_for_commit_lock
from vyos.defaults import vyos_configd_socket_path

context = zmq.Context()

request = {
    'type': 'node',
    'last': True,
    'data': '/usr/libexec/vyos/conf_mode/protocols_static.py',
}
request = json.dumps(request)

print("Waiting for commit lock...")
wait_for_commit_lock()

print("Connecting to vyos-configd server...")
socket = context.socket(zmq.REQ)
socket.connect(vyos_configd_socket_path)

print(f"Sending request {request}...")
socket.send_string(request)

message = socket.recv()
print(f"Received reply {request} [ {message} ]")

print("All done")
