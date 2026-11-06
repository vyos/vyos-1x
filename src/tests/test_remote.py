# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
import tempfile
import threading
import unittest
from base64 import b64encode
from unittest import mock
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from urllib.parse import urlsplit

from vyos.remote import HttpC

AUTH_HEADER = 'Basic ' + b64encode(b'vyos:secret').decode()
NETRC_AUTH_HEADER = 'Basic ' + b64encode(b'vyos_netrc:secret_netrc').decode()


class HeadRejectHandler(BaseHTTPRequestHandler):
    body = b'192.0.2.1\n'
    head_status = 405

    def do_HEAD(self):
        self.send_response(self.head_status)
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, format, *args):
        pass


class Head405Handler(HeadRejectHandler):
    head_status = 405


class Head501Handler(HeadRejectHandler):
    head_status = 501


class RedirectHandler(BaseHTTPRequestHandler):
    body = b'192.0.2.1\n'
    location = '/redirected.txt'

    def _respond(self, send_body):
        self.server.requests.append(
            (self.command, self.path, self.headers.get('Authorization'))
        )
        if self.path == '/list.txt':
            self.send_response(302)
            self.send_header(
                'Location', self.location.format(port=self.server.server_address[1])
            )
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(self.body)))
        self.end_headers()
        if send_body:
            self.wfile.write(self.body)

    def do_HEAD(self):
        self._respond(send_body=False)

    def do_GET(self):
        self._respond(send_body=True)

    def log_message(self, format, *args):
        pass


class SameOriginRedirectHandler(RedirectHandler):
    location = '/redirected.txt'


class CrossHostRedirectHandler(RedirectHandler):
    # Same server, but 'localhost' is a different host from '127.0.0.1'
    location = 'http://localhost:{port}/redirected.txt'


class TestHttpCDownload(unittest.TestCase):
    def _download_from_server(self, handler, userinfo=''):
        server = HTTPServer(('127.0.0.1', 0), handler)
        server.requests = []
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        url = f'http://{userinfo}127.0.0.1:{port}/list.txt'
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            client = HttpC(urlsplit(url))
            client.download(tmp_path)
            with open(tmp_path, 'rb') as downloaded:
                self.assertEqual(downloaded.read(), handler.body)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)
            os.unlink(tmp_path)

        return server.requests

    def _use_netrc_default_entry(self):
        # A 'default' entry matches any host, including a redirect target
        with tempfile.NamedTemporaryFile('w', delete=False) as netrc:
            netrc.write('default login vyos_netrc password secret_netrc\n')
        self.addCleanup(os.unlink, netrc.name)
        patcher = mock.patch.dict(os.environ, {'NETRC': netrc.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_download_without_head_support_405(self):
        self._download_from_server(Head405Handler)

    def test_download_without_head_support_501(self):
        self._download_from_server(Head501Handler)

    def test_download_redirect_to_other_host_drops_auth(self):
        requests = self._download_from_server(
            CrossHostRedirectHandler, userinfo='vyos:secret@'
        )
        self.assertEqual(
            requests,
            [
                ('HEAD', '/list.txt', AUTH_HEADER),
                ('HEAD', '/redirected.txt', None),
                ('GET', '/redirected.txt', None),
            ],
        )

    def test_download_redirect_to_same_origin_keeps_auth(self):
        requests = self._download_from_server(
            SameOriginRedirectHandler, userinfo='vyos:secret@'
        )
        self.assertEqual(
            requests,
            [
                ('HEAD', '/list.txt', AUTH_HEADER),
                ('HEAD', '/redirected.txt', AUTH_HEADER),
                ('GET', '/redirected.txt', AUTH_HEADER),
            ],
        )

    def test_download_redirect_to_other_host_ignores_netrc(self):
        self._use_netrc_default_entry()
        requests = self._download_from_server(
            CrossHostRedirectHandler, userinfo='vyos:secret@'
        )
        self.assertEqual(
            requests,
            [
                ('HEAD', '/list.txt', AUTH_HEADER),
                ('HEAD', '/redirected.txt', None),
                ('GET', '/redirected.txt', None),
            ],
        )

    def test_download_redirect_to_other_host_ignores_netrc_without_userinfo(self):
        self._use_netrc_default_entry()
        requests = self._download_from_server(CrossHostRedirectHandler)
        self.assertEqual(
            requests,
            [
                ('HEAD', '/list.txt', NETRC_AUTH_HEADER),
                ('HEAD', '/redirected.txt', None),
                ('GET', '/redirected.txt', None),
            ],
        )


if __name__ == '__main__':
    unittest.main()
