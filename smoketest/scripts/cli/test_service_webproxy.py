#!/usr/bin/env python3
#
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

import os
import unittest

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.util import cmd
from vyos.util import process_named_running
from vyos.util import read_file

PROCESS_NAME = 'squid'
PROXY_CONF = '/etc/squid/squid.conf'
base_path = ['service', 'webproxy']
listen_if = 'dum3632'
listen_ip = '192.0.2.1'

class TestServiceWebProxy(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        self.session.set(['interfaces', 'dummy', listen_if, 'address', listen_ip + '/32'])

    def tearDown(self):
        self.session.delete(['interfaces', 'dummy', listen_if])
        self.session.delete(base_path)
        self.session.commit()
        del self.session

    def test_01_basic_proxy(self):
        default_cache = '100'
        self.session.set(base_path + ['listen-address', listen_ip])

        # commit changes
        self.session.commit()

        config = read_file(PROXY_CONF)
        self.assertIn(f'http_port {listen_ip}:3128 intercept', config)
        self.assertIn(f'cache_dir ufs /var/spool/squid {default_cache} 16 256', config)
        self.assertIn(f'access_log /var/log/squid/access.log squid', config)

        # ACL verification
        self.assertIn(f'acl localhost src 127.0.0.1/32', config)
        self.assertIn(f'acl to_localhost dst 127.0.0.0/8', config)
        self.assertIn(f'acl net src all', config)
        self.assertIn(f'acl SSL_ports port 443', config)

        safe_ports = ['80', '21', '443', '873', '70', '210', '1025-65535', '280',
                      '488', '591', '777']
        for port in safe_ports:
            self.assertIn(f'acl Safe_ports port {port}', config)
        self.assertIn(f'acl CONNECT method CONNECT', config)

        self.assertIn(f'http_access allow manager localhost', config)
        self.assertIn(f'http_access deny manager', config)
        self.assertIn(f'http_access deny !Safe_ports', config)
        self.assertIn(f'http_access deny CONNECT !SSL_ports', config)
        self.assertIn(f'http_access allow localhost', config)
        self.assertIn(f'http_access allow net', config)
        self.assertIn(f'http_access deny all', config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_02_advanced_proxy(self):
        domain = '.vyos.io'
        cache_size = '900'
        port = '8080'
        min_obj_size = '128'
        max_obj_size = '8192'
        block_mine = ['application/pdf', 'application/x-sh']
        body_max_size = '4096'

        self.session.set(base_path + ['listen-address', listen_ip])
        self.session.set(base_path + ['append-domain', domain])
        self.session.set(base_path + ['default-port', port])
        self.session.set(base_path + ['cache-size', cache_size])
        self.session.set(base_path + ['disable-access-log'])

        self.session.set(base_path + ['minimum-object-size', min_obj_size])
        self.session.set(base_path + ['maximum-object-size', max_obj_size])

        self.session.set(base_path + ['outgoing-address', listen_ip])

        for mime in block_mine:
            self.session.set(base_path + ['reply-block-mime', mime])

        self.session.set(base_path + ['reply-body-max-size', body_max_size])

        # commit changes
        self.session.commit()

        config = read_file(PROXY_CONF)
        self.assertIn(f'http_port {listen_ip}:{port} intercept', config)
        self.assertIn(f'append_domain {domain}', config)
        self.assertIn(f'cache_dir ufs /var/spool/squid {cache_size} 16 256', config)
        self.assertIn(f'access_log none', config)
        self.assertIn(f'minimum_object_size {min_obj_size} KB', config)
        self.assertIn(f'maximum_object_size {max_obj_size} KB', config)
        self.assertIn(f'tcp_outgoing_address {listen_ip}', config)

        for mime in block_mine:
            self.assertIn(f'acl BLOCK_MIME rep_mime_type {mime}', config)
        self.assertIn(f'http_reply_access deny BLOCK_MIME', config)

        self.assertIn(f'reply_body_max_size {body_max_size} KB', config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_03_ldap_proxy_auth(self):
        auth_children = '20'
        cred_ttl = '120'
        realm = 'VyOS Webproxy'
        ldap_base_dn = 'DC=vyos,DC=net'
        ldap_server = 'ldap.vyos.net'
        ldap_bind_dn = 'CN=proxyuser,CN=Users,DC=example,DC=local'
        ldap_password = 'VyOS12345'
        ldap_attr = 'cn'
        ldap_filter = '(cn=%s)'

        self.session.set(base_path + ['listen-address', listen_ip, 'disable-transparent'])
        self.session.set(base_path + ['authentication', 'children', auth_children])
        self.session.set(base_path + ['authentication', 'credentials-ttl', cred_ttl])

        self.session.set(base_path + ['authentication', 'realm', realm])
        self.session.set(base_path + ['authentication', 'method', 'ldap'])
        # check validate() - LDAP authentication is enabled, but server not set
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(base_path + ['authentication', 'ldap', 'server', ldap_server])

        # check validate() - LDAP password can not be set when bind-dn is not define
        self.session.set(base_path + ['authentication', 'ldap', 'password', ldap_password])
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(base_path + ['authentication', 'ldap', 'bind-dn', ldap_bind_dn])

        # check validate() - LDAP base-dn must be set
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(base_path + ['authentication', 'ldap', 'base-dn', ldap_base_dn])

        self.session.set(base_path + ['authentication', 'ldap', 'username-attribute', ldap_attr])
        self.session.set(base_path + ['authentication', 'ldap', 'filter-expression', ldap_filter])

        # commit changes
        self.session.commit()

        config = read_file(PROXY_CONF)
        self.assertIn(f'http_port {listen_ip}:3128', config) # disable-transparent

        # Now verify LDAP settings
        self.assertIn(f'auth_param basic children {auth_children}', config)
        self.assertIn(f'auth_param basic credentialsttl {cred_ttl} minute', config)
        self.assertIn(f'auth_param basic realm {realm}', config)
        self.assertIn(f'auth_param basic program /usr/lib/squid/basic_ldap_auth -v 3 -b "{ldap_base_dn}" -D "{ldap_bind_dn}" -w {ldap_password} -f {ldap_filter} -u {ldap_attr} -p 389 -R -h {ldap_server}', config)
        self.assertIn(f'acl auth proxy_auth REQUIRED', config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_04_cache_peer(self):
        self.session.set(base_path + ['listen-address', listen_ip])

        cache_peers = {
            'foo' : '192.0.2.1',
            'bar' : '192.0.2.2',
            'baz' : '192.0.2.3',
        }
        for peer in cache_peers:
            self.session.set(base_path + ['cache-peer', peer, 'address', cache_peers[peer]])
            if peer == 'baz':
                self.session.set(base_path + ['cache-peer', peer, 'type', 'sibling'])

        # commit changes
        self.session.commit()

        config = read_file(PROXY_CONF)
        self.assertIn('never_direct allow all', config)

        for peer in cache_peers:
            address = cache_peers[peer]
            if peer == 'baz':
                self.assertIn(f'cache_peer {address} sibling 3128 0 no-query default', config)
            else:
                self.assertIn(f'cache_peer {address} parent 3128 0 no-query default', config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_05_basic_squidguard(self):
        default_cache = '100'
        local_block = ['192.0.0.1', '10.0.0.1', 'block.vyos.net']

        self.session.set(base_path + ['listen-address', listen_ip])
        self.session.set(base_path + ['url-filtering', 'squidguard', 'log', 'all'])
        for block in local_block:
            self.session.set(base_path + ['url-filtering', 'squidguard', 'local-block', block])

        # commit changes
        self.session.commit()

        # Check regular Squid config
        config = read_file(PROXY_CONF)
        self.assertIn(f'http_port {listen_ip}:3128 intercept', config)

        self.assertIn(f'redirect_program /usr/bin/squidGuard -c /etc/squidguard/squidGuard.conf', config)
        self.assertIn(f'redirect_children 8', config)

        # Check SquidGuard config
        sg_config = read_file('/etc/squidguard/squidGuard.conf')
        self.assertIn(f'log blacklist.log', sg_config)

        # The following are rewrite strings to force safe/strict search for
        # several popular search engines.
        self.assertIn(r"s@(.*\.google\..*/(custom|search|images|groups|news)?.*q=.*)@\1\&safe=active@i", sg_config)
        self.assertIn(r"s@(.*\..*/yandsearch?.*text=.*)@\1\&fyandex=1@i", sg_config)
        self.assertIn(r"s@(.*\.yahoo\..*/search.*p=.*)@\1\&vm=r@i", sg_config)
        self.assertIn(r"s@(.*\.live\..*/.*q=.*)@\1\&adlt=strict@i", sg_config)
        self.assertIn(r"s@(.*\.msn\..*/.*q=.*)@\1\&adlt=strict@i", sg_config)
        self.assertIn(r"s@(.*\.bing\..*/search.*q=.*)@\1\&adlt=strict@i", sg_config)

        # URL lists
        self.assertIn(r'dest local-ok-default {', sg_config)
        self.assertIn(f'domainlist     local-ok-default/domains', sg_config)
        self.assertIn(r'dest local-ok-url-default {', sg_config)
        self.assertIn(f'urllist        local-ok-url-default/urls', sg_config)

        # Redirect - default value
        self.assertIn(f'redirect 302:http://block.vyos.net', sg_config)

        # local-block database
        blocklist = read_file('/opt/vyatta/etc/config/url-filtering/squidguard/db/local-block-default/domains')
        for block in local_block:
            self.assertIn(f'{block}', blocklist)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))


if __name__ == '__main__':
    unittest.main()
