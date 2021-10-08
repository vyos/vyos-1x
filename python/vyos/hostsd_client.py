import json
import zmq

SOCKET_PATH = "ipc:///run/vyos-hostsd/vyos-hostsd.sock"

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
            else:
                return reply["data"]
        except zmq.error.Again:
            raise VyOSHostsdError("Could not connect to vyos-hostsd")

    def add_name_servers(self, data):
        msg = {'type': 'name_servers', 'op': 'add', 'data': data}
        self._communicate(msg)

    def delete_name_servers(self, data):
        msg = {'type': 'name_servers', 'op': 'delete', 'data': data}
        self._communicate(msg)

    def get_name_servers(self, tag_regex):
        msg = {'type': 'name_servers', 'op': 'get', 'tag_regex': tag_regex}
        return self._communicate(msg)

    def add_name_server_tags_recursor(self, data):
        msg = {'type': 'name_server_tags_recursor', 'op': 'add', 'data': data}
        self._communicate(msg)

    def delete_name_server_tags_recursor(self, data):
        msg = {'type': 'name_server_tags_recursor', 'op': 'delete', 'data': data}
        self._communicate(msg)

    def get_name_server_tags_recursor(self):
        msg = {'type': 'name_server_tags_recursor', 'op': 'get'}
        return self._communicate(msg)

    def add_name_server_tags_system(self, data):
        msg = {'type': 'name_server_tags_system', 'op': 'add', 'data': data}
        self._communicate(msg)

    def delete_name_server_tags_system(self, data):
        msg = {'type': 'name_server_tags_system', 'op': 'delete', 'data': data}
        self._communicate(msg)

    def get_name_server_tags_system(self):
        msg = {'type': 'name_server_tags_system', 'op': 'get'}
        return self._communicate(msg)

    def add_forward_zones(self, data):
        msg = {'type': 'forward_zones', 'op': 'add', 'data': data}
        self._communicate(msg)

    def delete_forward_zones(self, data):
        msg = {'type': 'forward_zones', 'op': 'delete', 'data': data}
        self._communicate(msg)

    def get_forward_zones(self):
        msg = {'type': 'forward_zones', 'op': 'get'}
        return self._communicate(msg)

    def add_authoritative_zones(self, data):
        msg = {'type': 'authoritative_zones', 'op': 'add', 'data': data}
        self._communicate(msg)

    def delete_authoritative_zones(self, data):
        msg = {'type': 'authoritative_zones', 'op': 'delete', 'data': data}
        self._communicate(msg)

    def get_authoritative_zones(self):
        msg = {'type': 'authoritative_zones', 'op': 'get'}
        return self._communicate(msg)

    def add_search_domains(self, data):
        msg = {'type': 'search_domains', 'op': 'add', 'data': data}
        self._communicate(msg)

    def delete_search_domains(self, data):
        msg = {'type': 'search_domains', 'op': 'delete', 'data': data}
        self._communicate(msg)

    def get_search_domains(self, tag_regex):
        msg = {'type': 'search_domains', 'op': 'get', 'tag_regex': tag_regex}
        return self._communicate(msg)

    def add_hosts(self, data):
        msg = {'type': 'hosts', 'op': 'add', 'data': data}
        self._communicate(msg)

    def delete_hosts(self, data):
        msg = {'type': 'hosts', 'op': 'delete', 'data': data}
        self._communicate(msg)

    def get_hosts(self, tag_regex):
        msg = {'type': 'hosts', 'op': 'get', 'tag_regex': tag_regex}
        return self._communicate(msg)

    def set_host_name(self, host_name, domain_name):
        msg = {
            'type': 'host_name',
            'op': 'set',
            'data': {
                'host_name': host_name,
                'domain_name': domain_name,
            }
        }
        self._communicate(msg)

    def apply(self):
        msg = {'op': 'apply'}
        return self._communicate(msg)
