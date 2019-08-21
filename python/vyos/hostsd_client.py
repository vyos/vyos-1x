import json

import zmq


SOCKET_PATH = "ipc:///run/vyos-hostsd.sock"


class VyOSHostsdError(Exception):
    pass


class Client(object):
    def __init__(self):
        try:
            context = zmq.Context()
            self.__socket = context.socket(zmq.REQ)
            self.__socket.RCVTIMEO = 10000 #ms
            self.__socket.setsockopt(zmq.LINGER, 0)
            self.__socket.connect(SOCKET_PATH)
        except zmq.error.Again:
            raise VyOSHostsdError("Could not connect to vyos-hostsd")

    def _communicate(self, msg):
        try:
            request = json.dumps(msg).encode()
            self.__socket.send(request)

            reply_msg = self.__socket.recv().decode()
            reply = json.loads(reply_msg)
            if 'error' in reply:
                raise VyOSHostsdError(reply['error'])
        except zmq.error.Again:
            raise VyOSHostsdError("Could not connect to vyos-hostsd")

    def set_host_name(self, host_name, domain_name, search_domains):
        msg = {
            'type': 'host_name',
            'op': 'set',
            'data': {
                'host_name': host_name,
                'domain_name': domain_name,
                'search_domains': search_domains
            }
        }
        self._communicate(msg)

    def add_hosts(self, tag, hosts):
        msg = {'type': 'hosts', 'op': 'add',  'tag': tag, 'data': hosts}
        self._communicate(msg)

    def delete_hosts(self, tag):
        msg = {'type': 'hosts', 'op': 'delete', 'tag': tag}
        self._communicate(msg)

    def add_name_servers(self, tag, servers):
        msg = {'type': 'name_servers', 'op': 'add', 'tag': tag, 'data': servers}
        self._communicate(msg)

    def delete_name_servers(self, tag):
        msg = {'type': 'name_servers', 'op': 'delete', 'tag': tag}
        self._communicate(msg)
