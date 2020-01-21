#!/usr/bin/env python3

import os
import re
import unittest

import vyos.config
import vyos.configsession
import vyos.util as util

RESOLV_CONF = '/etc/resolv.conf'

test_servers = ['192.0.2.10', '2001:db8:1::100']

base_path = ['system', 'name-server']


def get_name_servers():
  resolv_conf = util.read_file(RESOLV_CONF)
  return re.findall(r'\n?nameserver\s+(.*)', resolv_conf)

class TestSystemNameServer(unittest.TestCase):
    def setUp(self):
        self.session = vyos.configsession.ConfigSession(os.getpid())
        env = self.session.get_session_env()
        self.config = vyos.config.Config(session_env=env)

        # Delete existing name servers
        self.session.delete(base_path)
        self.session.commit()

    def test_add_server(self):
        """ Check if server is added to resolv.conf """
        for s in test_servers:
            self.session.set(base_path + [s])
        self.session.commit()

        servers = get_name_servers()
        for s in servers:
            self.assertTrue(s in servers)

    def test_delete_server(self):
        """ Test if a deleted server disappears from resolv.conf """
        for s in test_servers:
          self.session.delete(base_path + [s])
        self.session.commit()

        servers = get_name_servers()
        for s in servers:
            self.assertTrue(test_server_1 not in servers)

if __name__ == '__main__':
    unittest.main()

