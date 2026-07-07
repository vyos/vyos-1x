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
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from urllib.parse import urlsplit

from vyos.remote import HttpC


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


class TestHttpCDownload(unittest.TestCase):
    def _download_from_server(self, handler):
        server = HTTPServer(('127.0.0.1', 0), handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        url = f'http://127.0.0.1:{port}/list.txt'
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

    def test_download_without_head_support_405(self):
        self._download_from_server(Head405Handler)

    def test_download_without_head_support_501(self):
        self._download_from_server(Head501Handler)


if __name__ == '__main__':
    unittest.main()