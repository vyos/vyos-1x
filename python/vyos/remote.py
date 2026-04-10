# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
import pwd
import shutil
import socket
import ssl
import stat
import sys
import tempfile
import urllib.parse
import gzip

from contextlib import contextmanager
from pathlib import Path

from ftplib import FTP
from ftplib import FTP_TLS
from ftplib import _GLOBAL_DEFAULT_TIMEOUT
from ftplib import error_reply
from ftplib import parse150

from paramiko import SSHClient
from paramiko import SSHException
from paramiko import MissingHostKeyPolicy
from ftplib import FTP
from ftplib import FTP_TLS
from ftplib import _GLOBAL_DEFAULT_TIMEOUT
from ftplib import error_reply
from ftplib import parse150
from requests import Session
from requests.adapters import HTTPAdapter
from urllib.parse import urlsplit
from urllib.parse import urlunsplit
from urllib3 import PoolManager
from urllib3.connection import HTTPConnection

from vyos.progressbar import Progressbar
from vyos.utils.io import ask_yes_no
from vyos.utils.io import is_interactive
from vyos.utils.io import print_error
from vyos.utils.misc import begin
from vyos.utils.process import cmd
from vyos.utils.process import rc_cmd
from vyos.version import get_version
from vyos.base import Warning
from vyos.defaults import directories

CHUNK_SIZE = 8192

class InteractivePolicy(MissingHostKeyPolicy):
    """
    Paramiko policy for interactively querying the user on whether to proceed
     with SSH connections to unknown hosts.
    """
    def missing_host_key(self, client, hostname, key):
        print_error(f"Host '{hostname}' not found in known hosts.")
        print_error('Fingerprint: ' + key.get_fingerprint().hex())
        if not sys.stdin.isatty():
            return
        if not ask_yes_no('Do you wish to continue?'):
            raise SSHException(f"Cannot connect to unknown host '{hostname}'.")
        if client._host_keys_filename is None:
            Warning('no \'known_hosts\' file; create to store keys permanently')
            return
        if ask_yes_no('Do you wish to permanently add this host/key pair to known_hosts file?'):
            client._host_keys.add(hostname, key.get_name(), key)
            client.save_host_keys(client._host_keys_filename)

class SourceAdapter(HTTPAdapter):
    """
    urllib3 transport adapter for setting source addresses per session.
    """
    def __init__(self, source_pair, vrf=None, *args, **kwargs):
        self._source_pair = source_pair
        self._socket_options = list(HTTPConnection.default_socket_options)

        # Linux VRF binding (requires privileges)
        if vrf:
            self._socket_options.append(
                (socket.SOL_SOCKET, socket.SO_BINDTODEVICE, (vrf + "\0").encode())
            )

        super(SourceAdapter, self).__init__(*args, **kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        pool_kwargs["source_address"] = self._source_pair
        pool_kwargs["socket_options"] = self._socket_options
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            **pool_kwargs
        )

@contextmanager
def umask(mask: int):
    """
    Context manager that temporarily sets the process umask.
    """
    import os
    oldmask = os.umask(mask)
    try:
        yield
    finally:
        os.umask(oldmask)

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

class VRFFTPMixin:
    """Shared VRF support for FTP/FTPS sockets (control + data)."""
    def __init__(self, *args, vrf=None, **kwargs):
        self._vrf = vrf.encode() + b"\0" if vrf else None
        super().__init__(*args, **kwargs)

    def _bind_vrf(self, sock):
        if self._vrf:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, self._vrf)
        return sock

    def _create_vrf_connection(self, address, timeout, source_address=None):
        host, port = address
        err = None
        for res in socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM):
            af, socktype, proto, _, sa = res
            sock = None
            try:
                sock = socket.socket(af, socktype, proto)
                self._bind_vrf(sock)  # bind VRF BEFORE connect
                if timeout is not _GLOBAL_DEFAULT_TIMEOUT:
                    sock.settimeout(timeout)
                if source_address:
                    sock.bind(source_address)
                sock.connect(sa)
                return sock
            except OSError as e:
                err = e
                if sock is not None:
                    sock.close()
        if err is not None:
            raise err
        raise OSError("getaddrinfo returns an empty list")

    def connect(self, host="", port=0, timeout=-999, source_address=None):
        if host:
            self.host = host
        if port:
            self.port = port
        if timeout != -999:
            self.timeout = timeout

        self.sock = self._create_vrf_connection(
            (self.host, self.port), self.timeout, source_address
        )
        self.af = self.sock.family
        self.file = self.sock.makefile('r', encoding=self.encoding)
        self.welcome = self.getresp()
        return self.welcome

    def ntransfercmd(self, cmd, rest=None):
        size = None
        if self.passiveserver:
            host, port = self.makepasv()
            conn = self._create_vrf_connection(
                (host, port), self.timeout, self.source_address
            )
            try:
                if rest is not None:
                    self.sendcmd("REST %s" % rest)
                resp = self.sendcmd(cmd)
                if resp[0] == '2':
                    resp = self.getresp()
                if resp[0] != '1':
                    raise error_reply(resp)
            except Exception:
                conn.close()
                raise
        else:
            with self.makeport() as sock:
                if rest is not None:
                    self.sendcmd("REST %s" % rest)
                resp = self.sendcmd(cmd)
                if resp[0] == '2':
                    resp = self.getresp()
                if resp[0] != '1':
                    raise error_reply(resp)
                conn, _ = sock.accept()
                if self.timeout is not _GLOBAL_DEFAULT_TIMEOUT:
                    conn.settimeout(self.timeout)
                self._bind_vrf(conn)

        if resp[:3] == '150':
            size = parse150(resp)
        return conn, size

class VRF_FTP(VRFFTPMixin, FTP):
    """FTP client with VRF binding support."""
    pass

class VRF_FTP_TLS(VRFFTPMixin, FTP_TLS):
    """FTPS client with VRF binding support."""
    pass

class FtpC:
    def __init__(self,
                 url,
                 progressbar=False,
                 check_space=False,
                 source_host='',
                 source_port=0,
                 timeout=10,
                 vrf=None):
        self.secure = url.scheme == 'ftps'
        self.hostname = url.hostname
        self.path = url.path
        self.username = url.username or os.getenv('REMOTE_USERNAME', 'anonymous')
        self.password = url.password or os.getenv('REMOTE_PASSWORD', '')
        self.port = url.port or 21
        self.source = (source_host, source_port)
        self.progressbar = progressbar
        self.check_space = check_space
        self.timeout = timeout
        self.vrf = vrf

    def _establish(self):
        if self.secure:
            return VRF_FTP_TLS(source_address=self.source,
                              context=ssl.create_default_context(),
                              timeout=self.timeout,
                              vrf=self.vrf)
        else:
            return VRF_FTP(source_address=self.source,
                           timeout=self.timeout,
                           vrf=self.vrf)

    def download(self, location: str):
        # Open the file upfront before establishing connection.
        with open(location, 'wb') as f, self._establish() as conn:
            conn.connect(self.hostname, self.port)
            conn.login(self.username, self.password)
            # Set secure connection over TLS.
            if self.secure:
                conn.prot_p()
            # Almost all FTP servers support the `SIZE' command.
            size = conn.size(self.path)
            if self.check_space:
                check_storage(location, size)
            # No progressbar if we can't determine the size or if the file is too small.
            if self.progressbar and size and size > CHUNK_SIZE:
                with Progressbar(CHUNK_SIZE / size) as p:
                    callback = lambda block: begin(f.write(block), p.increment())
                    conn.retrbinary('RETR ' + self.path, callback, CHUNK_SIZE)
            else:
                conn.retrbinary('RETR ' + self.path, f.write, CHUNK_SIZE)

    def upload(self, location: str):
        size = os.path.getsize(location)
        with open(location, 'rb') as f, self._establish() as conn:
            conn.connect(self.hostname, self.port)
            conn.login(self.username, self.password)
            if self.secure:
                conn.prot_p()
            if self.progressbar and size and size > CHUNK_SIZE:
                with Progressbar(CHUNK_SIZE / size) as p:
                    conn.storbinary('STOR ' + self.path, f, CHUNK_SIZE, lambda block: p.increment())
            else:
                conn.storbinary('STOR ' + self.path, f, CHUNK_SIZE)

class SshC:
    known_hosts = os.path.expanduser('~/.ssh/known_hosts')
    def __init__(self,
                 url,
                 progressbar=False,
                 check_space=False,
                 source_host='',
                 source_port=0,
                 timeout=10.0,
                 vrf=None):
        self.hostname = url.hostname
        self.path = url.path
        self.username = url.username or os.getenv('REMOTE_USERNAME')
        self.password = url.password or os.getenv('REMOTE_PASSWORD')
        self.port = url.port or 22
        self.source = (source_host, source_port)
        self.progressbar = progressbar
        self.check_space = check_space
        self.timeout = timeout
        self.vrf = vrf

    def _establish(self):
        ssh = SSHClient()
        ssh.load_system_host_keys()
        # Try to load from a user-local known hosts file if one exists.
        if os.path.exists(self.known_hosts):
            ssh.load_host_keys(self.known_hosts)
        ssh.set_missing_host_key_policy(InteractivePolicy())
        # Create the socket manually so VRF/device binding is applied before
        # connect(), while still trying IPv4/IPv6 candidates on dual-stack systems.
        sock = None
        last_error = None
        for family, socktype, proto, _, sockaddr in socket.getaddrinfo(
                self.hostname, self.port, type=socket.SOCK_STREAM):
            try:
                sock = socket.socket(family, socktype, proto)
                sock.settimeout(self.timeout)
                if self.source != ('', 0):
                    sock.bind(self.source)
                if self.vrf:
                    vrf = (self.vrf + "\0").encode()
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, vrf)
                sock.connect(sockaddr)
                break
            except OSError as err:
                last_error = err
                if sock is not None:
                    sock.close()
                sock = None
        if sock is None:
            raise last_error

        ssh.connect(self.hostname, self.port, self.username, self.password, sock=sock)
        return ssh

    def download(self, location: str):
        with self._establish() as ssh, ssh.open_sftp() as sftp:
            if self.check_space:
                check_storage(location, sftp.stat(self.path).st_size)
            if self.progressbar:
                with Progressbar() as p:
                    sftp.get(self.path, location, callback=p.progress)
            else:
                sftp.get(self.path, location)

    def upload(self, location: str):
        with self._establish() as ssh, ssh.open_sftp() as sftp:
            # A file exists at this destination. We're simply going to clobber it.
            # This is our default fallback
            path = self.path
            try:
                # If the remote path is a directory, use the original filename.
                if stat.S_ISDIR(sftp.stat(self.path).st_mode):
                    path = os.path.join(self.path, os.path.basename(location))
            except IOError:
                pass

            if self.progressbar:
                with Progressbar() as p:
                    sftp.put(location, path, callback=p.progress)
            else:
                sftp.put(location, path)

class HttpC:
    def __init__(self,
                 url,
                 progressbar=False,
                 check_space=False,
                 source_host='',
                 source_port=0,
                 timeout=10.0,
                 vrf=None):
        self.urlstring = urllib.parse.urlunsplit(url)
        self.progressbar = progressbar
        self.check_space = check_space
        self.source_pair = (source_host, source_port)
        self.username = url.username or os.getenv('REMOTE_USERNAME')
        self.password = url.password or os.getenv('REMOTE_PASSWORD')
        self.timeout = timeout
        self.vrf = vrf

    def _establish(self):
        session = Session()
        adapter = SourceAdapter(self.source_pair, vrf=self.vrf)
        session.mount(self.urlstring, adapter)
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
            with s.head(self.urlstring,
                        allow_redirects=True,
                        timeout=self.timeout) as r:
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
            with s.get(final_urlstring, stream=True,
                       timeout=self.timeout) as r, open(location, 'wb') as f:
                if self.progressbar and size:
                    with Progressbar(CHUNK_SIZE / size) as p:
                        for chunk in iter(lambda: begin(p.increment(), r.raw.read(CHUNK_SIZE)), b''):
                            f.write(chunk)
                else:
                    # We'll try to stream the download directly with `copyfileobj()` so that large
                    #  files (like entire VyOS images) don't occupy much memory.
                    shutil.copyfileobj(r.raw, f)

    def upload(self, location: str):
        # Does not yet support progressbars.
        with self._establish() as s, open(location, 'rb') as f:
            s.post(self.urlstring,
                   data=f,
                   allow_redirects=True,
                   timeout=self.timeout)


class TftpC:
    # We simply allow `curl` to take over because
    # 1. TFTP is rather simple.
    # 2. Since there's no concept authentication, we don't need to deal with keys/passwords.
    # 3. It would be a waste to import, audit and maintain a third-party library for TFTP.
    # 4. I'd rather not implement the entire protocol here, no matter how simple it is.
    def __init__(self,
                 url,
                 progressbar=False,
                 check_space=False,
                 source_host=None,
                 source_port=0,
                 timeout=10,
                 vrf=None):
        source_option = f'--interface {source_host} --local-port {source_port}' if source_host else ''
        progress_flag = '--progress-bar' if progressbar else '--silent'
        self.command = f'curl {source_option} {progress_flag} --connect-timeout {timeout}'
        self.urlstring = urllib.parse.urlunsplit(url)
        self.vrf = vrf

    def download(self, location: str):
        with open(location, 'wb') as f:
            f.write(cmd(f'{self.command} "{self.urlstring}"',
                        vrf=self.vrf).encode())

    def upload(self, location: str):
        print(f'{self.command} "{self.urlstring}"')
        with open(location, 'rb') as f:
            cmd(f'{self.command} --upload-file - "{self.urlstring}"',
                input=f.read(), vrf=self.vrf)

class GitC:
    def __init__(self,
                 url,
                 progressbar=False,
                 check_space=False,
                 source_host=None,
                 source_port=0,
                 timeout=10,
                 vrf=None):
        self.command = ['git']
        self.vrf = vrf
        self.url = url
        self.urlstring = urllib.parse.urlunsplit(url)
        if self.urlstring.startswith("git+"):
            self.urlstring = self.urlstring.replace("git+", "", 1)

    def download(self, location: str):
        raise NotImplementedError("not supported")

    @umask(0o077)
    def upload(self, location: str):
        scheme = self.url.scheme
        _, _, scheme = scheme.partition("+")
        netloc = self.url.netloc
        url = Path(self.url.path).parent
        with tempfile.TemporaryDirectory(prefix="git-commit-archive-") as directory:
            # Determine username, fullname, email for Git commit
            pwd_entry = pwd.getpwuid(os.getuid())
            user = pwd_entry.pw_name
            name = pwd_entry.pw_gecos.split(",")[0] or user
            fqdn = socket.getfqdn()
            email = f"{user}@{fqdn}"

            # environment vars for our git commands
            env = {
                **os.environ,
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_AUTHOR_NAME": name,
                "GIT_AUTHOR_EMAIL": email,
                "GIT_COMMITTER_NAME": name,
                "GIT_COMMITTER_EMAIL": email,
            }

            # build ssh command for git
            ssh_command = ["ssh"]

            # if we are not interactive, we use StrictHostKeyChecking=yes to avoid any prompts
            if not sys.stdout.isatty():
                ssh_command += ["-o", "StrictHostKeyChecking=yes"]

            env["GIT_SSH_COMMAND"] = " ".join(ssh_command)

            # git clone
            path_repository = Path(directory) / "repository"
            scheme = f"{scheme}://" if scheme else ""
            rc, out = rc_cmd(
                self.command + ["clone", f"{scheme}{netloc}{url}", str(path_repository), "--depth=1"],
                env=env,
                shell=False,
                vrf=self.vrf,
            )
            if rc:
                raise Exception(out)

            # git add
            filename = Path(Path(self.url.path).name).stem
            dst = path_repository / filename
            shutil.copy2(location, dst)
            rc, out = rc_cmd(
                self.command + ["-C", str(path_repository), "add", filename],
                env=env,
                shell=False,
            )

            # git commit -m
            commit_message = os.environ.get("COMMIT_COMMENT", "commit")
            rc, out = rc_cmd(
                self.command + ["-C", str(path_repository), "commit", "-m", commit_message],
                env=env,
                shell=False,
            )

            # git push
            rc, out = rc_cmd(
                self.command + ["-C", str(path_repository), "push"],
                env=env,
                shell=False,
                vrf=self.vrf,
            )
            if rc:
                raise Exception(out)


def urlc(urlstring, *args, **kwargs):
    """
    Dynamically dispatch the appropriate protocol class.
    """
    url_classes = {
        "http": HttpC,
        "https": HttpC,
        "ftp": FtpC,
        "ftps": FtpC,
        "sftp": SshC,
        "ssh": SshC,
        "scp": SshC,
        "tftp": TftpC,
        "git": GitC,
    }
    url = urllib.parse.urlsplit(urlstring)
    scheme, _, _ = url.scheme.partition("+")
    try:
        return url_classes[scheme](url, *args, **kwargs)
    except KeyError:
        raise ValueError(f'Unsupported URL scheme: "{scheme}"')

def download(local_path, urlstring, progressbar=False, check_space=False,
             source_host='', source_port=0, timeout=10.0, raise_error=False):
    try:
        progressbar = progressbar and is_interactive()
        urlc(urlstring, progressbar, check_space, source_host, source_port, timeout).download(local_path)
    except Exception as err:
        if raise_error:
            raise
        print_error(f'Unable to download "{urlstring}": {err}')
        sys.exit(1)
    except KeyboardInterrupt:
        print_error('\nDownload aborted by user.')
        sys.exit(1)

def upload(local_path, urlstring, progressbar=False,
           source_host='', source_port=0, timeout=10.0, vrf=None):
    try:
        progressbar = progressbar and is_interactive()
        urlc(urlstring, progressbar, False, source_host, source_port, timeout, vrf).upload(local_path)
    except Exception as err:
        url = urlsplit(urlstring)
        _, _, netloc = url.netloc.rpartition('@')
        redacted_location = urlunsplit(url._replace(netloc=netloc))
        print_error(f'Unable to upload "{redacted_location}": {err}')
        sys.exit(1)
    except KeyboardInterrupt:
        print_error('\nUpload aborted by user.')
        sys.exit(1)

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


def get_config_file(file_in: str, file_out: str, source_host='', source_port=0):
    protocols = ['scp', 'sftp', 'http', 'https', 'ftp', 'tftp']
    config_dir = directories['config']

    with tempfile.NamedTemporaryFile() as tmp_file:
        if any(file_in.startswith(f'{x}://') for x in protocols):
            try:
                download(
                    tmp_file.name,
                    file_in,
                    check_space=True,
                    source_host='',
                    source_port=0,
                    raise_error=True,
                )
            except Exception as e:
                return e
            file_name = tmp_file.name
        else:
            full_path = os.path.realpath(file_in)
            if os.path.isfile(full_path):
                file_in = full_path
            else:
                file_in = os.path.join(config_dir, file_in)
                if not os.path.isfile(file_in):
                    return ValueError(f'No such file {file_in}')

            file_name = file_in

        if file_in.endswith('.gz'):
            try:
                with gzip.open(file_name, 'rb') as f_in:
                    with open(file_out, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            except Exception as e:
                return e
        else:
            shutil.copyfile(file_name, file_out)

    return None
