# Copyright 2021 VyOS maintainers and contributors <maintainers@vyos.io>
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
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import os
import shutil
import socket
import ssl
import stat
import sys
import tempfile
import urllib.parse

from ftplib import FTP
from ftplib import FTP_TLS

from paramiko import SSHClient
from paramiko import MissingHostKeyPolicy

from requests import Session
from requests.adapters import HTTPAdapter
from requests.packages.urllib3 import PoolManager

from vyos.util import ask_yes_no
from vyos.util import begin
from vyos.util import cmd
from vyos.util import make_incremental_progressbar
from vyos.util import make_progressbar
from vyos.util import print_error
from vyos.version import get_version


CHUNK_SIZE = 8192

class InteractivePolicy(MissingHostKeyPolicy):
    """
    Paramiko policy for interactively querying the user on whether to proceed
     with SSH connections to unknown hosts.
    """
    def missing_host_key(self, client, hostname, key):
        print_error(f"Host '{hostname}' not found in known hosts.")
        print_error('Fingerprint: ' + key.get_fingerprint().hex())
        if ask_yes_no('Do you wish to continue?'):
            if client._host_keys_filename\
               and ask_yes_no('Do you wish to permanently add this host/key pair to known hosts?'):
                client._host_keys.add(hostname, key.get_name(), key)
                client.save_host_keys(client._host_keys_filename)
        else:
            raise SSHException(f"Cannot connect to unknown host '{hostname}'.")

class SourceAdapter(HTTPAdapter):
    """
    urllib3 transport adapter for setting source addresses per session.
    """
    def __init__(self, source_pair, *args, **kwargs):
        # A source pair is a tuple of a source host string and source port respectively.
        # Supply '' and 0 respectively for default values.
        self._source_pair = source_pair
        super(SourceAdapter, self).__init__(*args, **kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize,
            block=block, source_address=self._source_pair)


def check_storage(path, size):
    """
    Check whether `path` has enough storage space for a transfer of `size` bytes.
    """
    path = os.path.abspath(os.path.expanduser(path))
    directory = path if os.path.isdir(path) else (os.path.dirname(os.path.expanduser(path)) or os.getcwd())
    # `size` can be None or 0 to indicate unknown size.
    if not size:
        print_error('Warning: Cannot determine size of remote file. Bravely continuing regardless.')
        return

    if size < 1024 * 1024:
        print_error(f'The file is {size / 1024.0:.3f} KiB.')
    else:
        print_error(f'The file is {size / (1024.0 * 1024.0):.3f} MiB.')

    # Will throw `FileNotFoundError' if `directory' is absent.
    if size > shutil.disk_usage(directory).free:
        raise OSError(f'Not enough disk space available in "{directory}".')


class FtpC:
    def __init__(self, url, progressbar=False, check_space=False, source_host='', source_port=0):
        self.secure = url.scheme == 'ftps'
        self.hostname = url.hostname
        self.path = url.path
        self.username = url.username or os.getenv('REMOTE_USERNAME', 'anonymous')
        self.password = url.password or os.getenv('REMOTE_PASSWORD', '')
        self.port = url.port or 21
        self.source = (source_host, source_port)
        self.progressbar = progressbar
        self.check_space = check_space

    def _establish(self):
        if self.secure:
            return FTP_TLS(source_address=self.source, context=ssl.create_default_context())
        else:
            return FTP(source_address=self.source)

    def download(self, location: str):
        # Open the file upfront before establishing connection.
        with open(location, 'wb') as f, self._establish() as conn:
            conn.connect(self.hostname, self.port)
            conn.login(self.username, self.password)
            # Set secure connection over TLS.
            if self.secure:
                conn.prot_p()
            # Almost all FTP servers support the `SIZE' command.
            if self.check_space:
                check_storage(path, conn.size(self.path))
            # No progressbar if we can't determine the size or if the file is too small.
            if self.progressbar and size and size > CHUNK_SIZE:
                progress = make_incremental_progressbar(CHUNK_SIZE / size)
                next(progress)
                callback = lambda block: begin(f.write(block), next(progress))
            else:
                callback = f.write
            conn.retrbinary('RETR ' + self.path, callback, CHUNK_SIZE)

    def upload(self, location: str):
        size = os.path.getsize(location)
        with open(location, 'rb') as f, self._establish() as conn:
            conn.connect(self.hostname, self.port)
            conn.login(self.username, self.password)
            if self.secure:
                conn.prot_p()
            if self.progressbar and size and size > CHUNK_SIZE:
                progress = make_incremental_progressbar(CHUNK_SIZE / size)
                next(progress)
                callback = lambda block: next(progress)
            else:
                callback = None
            conn.storbinary('STOR ' + self.path, f, CHUNK_SIZE, callback)

class SshC:
    known_hosts = os.path.expanduser('~/.ssh/known_hosts')
    def __init__(self, url, progressbar=False, check_space=False, source_host='', source_port=0):
        self.hostname = url.hostname
        self.path = url.path
        self.username = url.username or os.getenv('REMOTE_USERNAME')
        self.password = url.password or os.getenv('REMOTE_PASSWORD')
        self.port = url.port or 22
        self.source = (source_host, source_port)
        self.progressbar = progressbar
        self.check_space = check_space

    def _establish(self):
        ssh = SSHClient()
        ssh.load_system_host_keys()
        # Try to load from a user-local known hosts file if one exists.
        if os.path.exists(self.known_hosts):
            ssh.load_host_keys(self.known_hosts)
        ssh.set_missing_host_key_policy(InteractivePolicy())
        # `socket.create_connection()` automatically picks a NIC and an IPv4/IPv6 address family
        #  for us on dual-stack systems.
        sock = socket.create_connection((self.hostname, self.port), socket.getdefaulttimeout(), self.source)
        ssh.connect(self.hostname, self.port, self.username, self.password, sock=sock)
        return ssh

    def download(self, location: str):
        callback = make_progressbar() if self.progressbar else None
        with self._establish() as ssh, ssh.open_sftp() as sftp:
            if self.check_space:
                check_storage(location, sftp.stat(self.path).st_size)
            sftp.get(self.path, location, callback=callback)

    def upload(self, location: str):
        callback = make_progressbar() if self.progressbar else None
        with self._establish() as ssh, ssh.open_sftp() as sftp:
            try:
                # If the remote path is a directory, use the original filename.
                if stat.S_ISDIR(sftp.stat(self.path).st_mode):
                    path = os.path.join(self.path, os.path.basename(location))
                # A file exists at this destination. We're simply going to clobber it.
                else:
                    path = self.path
            # This path doesn't point at any existing file. We can freely use this filename.
            except IOError:
                path = self.path
            finally:
                sftp.put(location, path, callback=callback)


class HttpC:
    def __init__(self, url, progressbar=False, check_space=False, source_host='', source_port=0):
        self.urlstring = urllib.parse.urlunsplit(url)
        self.progressbar = progressbar
        self.check_space = check_space
        self.source_pair = (source_host, source_port)
        self.username = url.username or os.getenv('REMOTE_USERNAME')
        self.password = url.password or os.getenv('REMOTE_PASSWORD')

    def _establish(self):
        session = Session()
        session.mount(self.urlstring, SourceAdapter(self.source_pair))
        session.headers.update({'User-Agent': 'VyOS/' + get_version()})
        if self.username:
            session.auth = self.username, self.password
        return session

    def download(self, location: str):
        with self._establish() as s:
            # We ask for uncompressed downloads so that we don't have to deal with decoding.
            # Not only would it potentially mess up with the progress bar but
            # `shutil.copyfileobj(request.raw, file)` does not handle automatic decoding.
            s.headers.update({'Accept-Encoding': 'identity'})
            with s.head(self.urlstring, allow_redirects=True) as r:
                # Abort early if the destination is inaccessible.
                r.raise_for_status()
                # If the request got redirected, keep the last URL we ended up with.
                final_urlstring = r.url
                if r.history and self.progressbar:
                    print_error('Redirecting to ' + final_urlstring)
                # Check for the prospective file size.
                try:
                    size = int(r.headers['Content-Length'])
                # In case the server does not supply the header.
                except KeyError:
                    size = None
            if self.check_space:
                check_storage(location, size)
            with s.get(final_urlstring, stream=True) as r, open(location, 'wb') as f:
                if self.progressbar and size:
                    progress = make_incremental_progressbar(CHUNK_SIZE / size)
                    next(progress)
                    for chunk in iter(lambda: begin(next(progress), r.raw.read(CHUNK_SIZE)), b''):
                        f.write(chunk)
                else:
                    # We'll try to stream the download directly with `copyfileobj()` so that large
                    #  files (like entire VyOS images) don't occupy much memory.
                    shutil.copyfileobj(r.raw, f)

    def upload(self, location: str):
        # Does not yet support progressbars.
        with self._establish() as s, open(location, 'rb') as f:
            s.post(self.urlstring, data=f, allow_redirects=True)


class TftpC:
    # We simply allow `curl` to take over because
    # 1. TFTP is rather simple.
    # 2. Since there's no concept authentication, we don't need to deal with keys/passwords.
    # 3. It would be a waste to import, audit and maintain a third-party library for TFTP.
    # 4. I'd rather not implement the entire protocol here, no matter how simple it is.
    def __init__(self, url, progressbar=False, check_space=False, source_host=None, source_port=0):
        source_option = f'--interface {source_host} --local-port {source_port}' if source_host else ''
        progress_flag = '--progress-bar' if progressbar else '-s'
        self.command = f'curl {source_option} {progress_flag}'
        self.urlstring = urllib.parse.urlunsplit(url)

    def download(self, location: str):
        with open(location, 'wb') as f:
            f.write(cmd(f'{self.command} "{self.urlstring}"').encode())

    def upload(self, location: str):
        with open(location, 'rb') as f:
            cmd(f'{self.command} -T - "{self.urlstring}"', input=f.read())


def urlc(urlstring, *args, **kwargs):
    """
    Dynamically dispatch the appropriate protocol class.
    """
    url_classes = {'http': HttpC, 'https': HttpC, 'ftp': FtpC, 'ftps': FtpC, \
                   'sftp': SshC, 'ssh': SshC, 'scp': SshC, 'tftp': TftpC}
    url = urllib.parse.urlsplit(urlstring)
    try:
        return url_classes[url.scheme](url, *args, **kwargs)
    except KeyError:
        raise ValueError(f'Unsupported URL scheme: "{url.scheme}"')

def download(local_path, urlstring, *args, **kwargs):
    urlc(urlstring, *args, **kwargs).download(local_path)

def upload(local_path, urlstring, *args, **kwargs):
    urlc(urlstring, *args, **kwargs).upload(local_path)

def get_remote_config(urlstring, source_host='', source_port=0):
    """
    Quietly download a file and return it as a string.
    """
    temp = tempfile.NamedTemporaryFile(delete=False).name
    try:
        download(temp, urlstring, False, False, source_host, source_port)
        with open(temp, 'r') as f:
            return f.read()
    finally:
        os.remove(temp)

def friendly_download(local_path, urlstring, source_host='', source_port=0):
    """
    Download with a progress bar, reassuring messages and free space checks.
    """
    try:
        print_error('Downloading...')
        download(local_path, urlstring, True, True, source_host, source_port)
    except KeyboardInterrupt:
        print_error('\nDownload aborted by user.')
        sys.exit(1)
    except:
        import traceback
        print_error(f'Failed to download {urlstring}.')
        # There are a myriad different reasons a download could fail.
        # SSH errors, FTP errors, I/O errors, HTTP errors (403, 404...)
        # We omit the scary stack trace but print the error nevertheless.
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, None, 0, None, False)
        sys.exit(1)
    else:
        print_error('Download complete.')
        sys.exit(0)
