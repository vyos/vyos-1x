#!/usr/bin/env python3
#
# Copyright (C) 2020-2022 VyOS maintainers and contributors
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

import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.process import cmd
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file

PROCESS_NAME = 'squid'
PROXY_CONF = '/etc/squid/squid.conf'
base_path = ['service', 'webproxy']
listen_if = 'dum3632'
listen_ip = '192.0.2.1'

class TestServiceWebProxy(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        # call base-classes classmethod
        super(TestServiceWebProxy, cls).setUpClass()
        # create a test interfaces
        cls.cli_set(cls, ['interfaces', 'dummy', listen_if, 'address', listen_ip + '/32'])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['interfaces', 'dummy', listen_if])
        super(TestServiceWebProxy, cls).tearDownClass()

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def test_01_basic_proxy(self):
        default_cache = '100'
        self.cli_set(base_path + ['listen-address', listen_ip])

        # commit changes
        self.cli_commit()

        config = read_file(PROXY_CONF)
        self.assertIn(f'http_port {listen_ip}:3128 intercept', config)
        self.assertIn(f'cache_dir ufs /var/spool/squid {default_cache} 16 256', config)
        self.assertIn(f'access_log /var/log/squid/access.log squid', config)

        # ACL verification
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
        safe_port = '88'
        ssl_safe_port = '8443'

        self.cli_set(base_path + ['listen-address', listen_ip])
        self.cli_set(base_path + ['append-domain', domain])
        self.cli_set(base_path + ['default-port', port])
        self.cli_set(base_path + ['cache-size', cache_size])
        self.cli_set(base_path + ['disable-access-log'])

        self.cli_set(base_path + ['minimum-object-size', min_obj_size])
        self.cli_set(base_path + ['maximum-object-size', max_obj_size])

        self.cli_set(base_path + ['outgoing-address', listen_ip])

        for mime in block_mine:
            self.cli_set(base_path + ['reply-block-mime', mime])

        self.cli_set(base_path + ['reply-body-max-size', body_max_size])

        self.cli_set(base_path + ['safe-ports', safe_port])
        self.cli_set(base_path + ['ssl-safe-ports', ssl_safe_port])

        # commit changes
        self.cli_commit()

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

        self.assertIn(f'acl Safe_ports port {safe_port}', config)
        self.assertIn(f'acl SSL_ports port {ssl_safe_port}', config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_03_ldap_proxy_auth(self):
        auth_children = '20'
        cred_ttl = '120'
        realm = 'VyOS Webproxy'
        ldap_base_dn = 'DC=vyos,DC=net'
        ldap_server = 'ldap.vyos.net'
        ldap_bind_dn = f'CN=proxyuser,CN=Users,{ldap_base_dn}'
        ldap_password = 'VyOS12345'
        ldap_attr = 'cn'
        ldap_filter = '(cn=%s)'

        self.cli_set(base_path + ['listen-address', listen_ip, 'disable-transparent'])
        self.cli_set(base_path + ['authentication', 'children', auth_children])
        self.cli_set(base_path + ['authentication', 'credentials-ttl', cred_ttl])

        self.cli_set(base_path + ['authentication', 'realm', realm])
        self.cli_set(base_path + ['authentication', 'method', 'ldap'])
        # check validate() - LDAP authentication is enabled, but server not set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['authentication', 'ldap', 'server', ldap_server])

        # check validate() - LDAP password can not be set when bind-dn is not define
        self.cli_set(base_path + ['authentication', 'ldap', 'password', ldap_password])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['authentication', 'ldap', 'bind-dn', ldap_bind_dn])

        # check validate() - LDAP base-dn must be set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['authentication', 'ldap', 'base-dn', ldap_base_dn])

        self.cli_set(base_path + ['authentication', 'ldap', 'username-attribute', ldap_attr])
        self.cli_set(base_path + ['authentication', 'ldap', 'filter-expression', ldap_filter])
        self.cli_set(base_path + ['authentication', 'ldap', 'use-ssl'])

        # commit changes
        self.cli_commit()

        config = read_file(PROXY_CONF)
        self.assertIn(f'http_port {listen_ip}:3128', config) # disable-transparent

        # Now verify LDAP settings
        self.assertIn(f'auth_param basic children {auth_children}', config)
        self.assertIn(f'auth_param basic credentialsttl {cred_ttl} minute', config)
        self.assertIn(f'auth_param basic realm "{realm}"', config)
        self.assertIn(f'auth_param basic program /usr/lib/squid/basic_ldap_auth -v 3 -b "{ldap_base_dn}" -D "{ldap_bind_dn}" -w "{ldap_password}" -f "{ldap_filter}" -u "{ldap_attr}" -p 389 -ZZ -R -h "{ldap_server}"', config)
        self.assertIn(f'acl auth proxy_auth REQUIRED', config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_04_cache_peer(self):
        self.cli_set(base_path + ['listen-address', listen_ip])

        cache_peers = {
            'foo' : '192.0.2.1',
            'bar' : '192.0.2.2',
            'baz' : '192.0.2.3',
        }
        for peer in cache_peers:
            self.cli_set(base_path + ['cache-peer', peer, 'address', cache_peers[peer]])
            if peer == 'baz':
                self.cli_set(base_path + ['cache-peer', peer, 'type', 'sibling'])

        # commit changes
        self.cli_commit()

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
        # Create very basic local SquidGuard blacklist and verify its contents
        sg_db_dir = '/opt/vyatta/etc/config/url-filtering/squidguard/db'

        default_cache = '100'
        local_block = ['192.0.0.1', '10.0.0.1', 'block.vyos.net']
        local_block_url = ['foo.com/bar.html', 'bar.com/foo.htm']
        local_block_pattern = ['porn', 'cisco', 'juniper']
        local_ok = ['10.0.0.0', 'vyos.net']
        local_ok_url = ['vyos.net', 'vyos.io']

        self.cli_set(base_path + ['listen-address', listen_ip])
        self.cli_set(base_path + ['url-filtering', 'squidguard', 'log', 'all'])

        for block in local_block:
            self.cli_set(base_path + ['url-filtering', 'squidguard', 'local-block', block])
        for ok in local_ok:
            self.cli_set(base_path + ['url-filtering', 'squidguard', 'local-ok', ok])
        for url in local_block_url:
            self.cli_set(base_path + ['url-filtering', 'squidguard', 'local-block-url', url])
        for url in local_ok_url:
            self.cli_set(base_path + ['url-filtering', 'squidguard', 'local-ok-url', url])
        for pattern in local_block_pattern:
            self.cli_set(base_path + ['url-filtering', 'squidguard', 'local-block-keyword', pattern])

        # commit changes
        self.cli_commit()

        # Check regular Squid config
        config = read_file(PROXY_CONF)
        self.assertIn(f'http_port {listen_ip}:3128 intercept', config)

        self.assertIn(f'url_rewrite_program /usr/bin/squidGuard -c /etc/squidguard/squidGuard.conf', config)
        self.assertIn(f'url_rewrite_children 8', config)

        # Check SquidGuard config
        sg_config = read_file('/etc/squidguard/squidGuard.conf')
        self.assertIn(f'log blacklist.log', sg_config)

        # The following are rewrite strings to force safe/strict search for
        # several popular search engines.
        self.assertIn(r's@(.*\.google\..*/(custom|search|images|groups|news)?.*q=.*)@\1\&safe=active@i', sg_config)
        self.assertIn(r's@(.*\..*/yandsearch?.*text=.*)@\1\&fyandex=1@i', sg_config)
        self.assertIn(r's@(.*\.yahoo\..*/search.*p=.*)@\1\&vm=r@i', sg_config)
        self.assertIn(r's@(.*\.live\..*/.*q=.*)@\1\&adlt=strict@i', sg_config)
        self.assertIn(r's@(.*\.msn\..*/.*q=.*)@\1\&adlt=strict@i', sg_config)
        self.assertIn(r's@(.*\.bing\..*/search.*q=.*)@\1\&adlt=strict@i', sg_config)

        # URL lists
        self.assertIn(r'dest local-ok-default {', sg_config)
        self.assertIn(f'domainlist     local-ok-default/domains', sg_config)
        self.assertIn(r'dest local-ok-url-default {', sg_config)
        self.assertIn(f'urllist        local-ok-url-default/urls', sg_config)

        # Redirect - default value
        self.assertIn(f'redirect 302:http://block.vyos.net', sg_config)

        # local-block database
        tmp = cmd(f'sudo cat {sg_db_dir}/local-block-default/domains')
        for block in local_block:
            self.assertIn(f'{block}', tmp)

        tmp = cmd(f'sudo cat {sg_db_dir}/local-block-url-default/urls')
        for url in local_block_url:
            self.assertIn(f'{url}', tmp)

        tmp = cmd(f'sudo cat {sg_db_dir}/local-block-keyword-default/expressions')
        for pattern in local_block_pattern:
            self.assertIn(f'{pattern}', tmp)

        # local-ok database
        tmp = cmd(f'sudo cat {sg_db_dir}/local-ok-default/domains')
        for ok in local_ok:
            self.assertIn(f'{ok}', tmp)

        tmp = cmd(f'sudo cat {sg_db_dir}/local-ok-url-default/urls')
        for url in local_ok_url:
            self.assertIn(f'{url}', tmp)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))


if __name__ == '__main__':
    unittest.main(verbosity=2)
