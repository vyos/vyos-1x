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

from ftplib import FTP
import ipaddress
import math
import os
import shutil
import socket
import sys
import tempfile
import urllib.parse
import urllib.request as urlreq

from vyos.util import cmd, ask_yes_no
from vyos.version import get_version
from paramiko import SSHClient, SSHException, MissingHostKeyPolicy


# This is a hardcoded path and no environment variable can change it.
KNOWN_HOSTS_FILE = os.path.expanduser('~/.ssh/known_hosts')
CHUNK_SIZE = 8192

class InteractivePolicy(MissingHostKeyPolicy):
    """
    Policy for interactively querying the user on whether to proceed with
     SSH connections to unknown hosts.
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


## Helper routines
def print_error(str='', end='\n'):
    """
    Print `str` to stderr, terminated with `end`.
    Used for warnings and out-of-band messages to avoid mangling precious
     stdout output.
    """
    sys.stderr.write(str)
    sys.stderr.write(end)
    sys.stderr.flush()

def make_progressbar():
    """
    Make a procedure that takes two arguments `done` and `total` and prints a
     progressbar based on the ratio thereof, whose length is determined by the
     width of the terminal.
    """
    col, _ = shutil.get_terminal_size()
    col = max(col - 15, 20)
    def print_progressbar(done, total):
        if done <= total:
            increment = total / col
            length = math.ceil(done / increment)
            percentage = str(math.ceil(100 * done / total)).rjust(3)
            print_error(f'[{length * "#"}{(col - length) * "_"}] {percentage}%', '\r')
            # Print a newline so that the subsequent prints don't overwrite the full bar.
        if done == total:
            print_error()
    return print_progressbar

def make_incremental_progressbar(increment: float):
    """
    Make a generator that displays a progressbar that grows monotonically with
     every iteration.
    First call displays it at 0% and every subsequent iteration displays it
     at `increment` increments where 0.0 < `increment` < 1.0.
    Intended for FTP and HTTP transfers with stateless callbacks.
    """
    print_progressbar = make_progressbar()
    total = 0.0
    while total < 1.0:
        print_progressbar(total, 1.0)
        yield
        total += increment
    print_progressbar(1, 1)
    # Ignore further calls.
    while True:
        yield

def get_authentication_variables(default_username=None, default_password=None):
    """
    Return the environment variables `$REMOTE_USERNAME` and `$REMOTE_PASSWORD` and
     return the defaults provided if environment variables are empty or nonexistent.
    """
    username, password = os.getenv('REMOTE_USERNAME'), os.getenv('REMOTE_PASSWORD')
    # Fall back to defaults if the username variable doesn't exist or is an empty string.
    # Note that this is different from `os.getenv('REMOTE_USERNAME', default=default_username)`,
    #  as we want the username and the password to have the same behaviour.
    if not username:
        return (default_username, default_password)
    else:
        return (username, password)

def get_port_from_url(url):
    """
    Return the port number from the given `url` named tuple, fall back to
     the default if there isn't one.
    """
    defaults = {"http": 80, "https": 443, "ftp": 21, "tftp": 69,\
                "ssh": 22, "scp": 22, "sftp": 22}
    if url.port:
        return url.port
    else:
        return defaults[url.scheme]


## FTP routines
def upload_ftp(local_path, hostname, remote_path,\
               username='anonymous', password='', port=21,\
               source=None, progressbar=False):
    size = os.path.getsize(local_path)
    with FTP(source_address=source) as conn:
        conn.connect(hostname, port)
        conn.login(username, password)
        with open(local_path, 'rb') as file:
            if progressbar and size:
                progress = make_incremental_progressbar(CHUNK_SIZE / size)
                next(progress)
                callback = lambda block: next(progress)
            else:
                callback = None
            conn.storbinary(f'STOR {remote_path}', file, CHUNK_SIZE, callback)

def download_ftp(local_path, hostname, remote_path,\
                 username='anonymous', password='', port=21,\
                 source=None, progressbar=False):
    with FTP(source_address=source) as conn:
        conn.connect(hostname, port)
        conn.login(username, password)
        size = conn.size(remote_path)
        with open(local_path, 'wb') as file:
            # No progressbar if we can't determine the size.
            if progressbar and size:
                progress = make_incremental_progressbar(CHUNK_SIZE / size)
                next(progress)
                callback = lambda block: (file.write(block), next(progress))
            else:
                callback = file.write
            conn.retrbinary(f'RETR {remote_path}', callback, CHUNK_SIZE)

def get_ftp_file_size(hostname, remote_path,\
                      username='anonymous', password='', port=21,\
                      source=None):
    with FTP(source_address=source) as conn:
        conn.connect(hostname, port)
        conn.login(username, password)
        size = conn.size(remote_path)
        if size:
            return size
        else:
            # SIZE is an extension to the FTP specification, although it's extremely common.
            raise ValueError('Failed to receive file size from FTP server. \
            Perhaps the server does not implement the SIZE command?')


## SFTP/SCP routines
def transfer_sftp(mode, local_path, hostname, remote_path,\
                  username=None, password=None, port=22,\
                  source=None, progressbar=False):
    sock = None
    if source:
        # Check if the given string is an IPv6 address.
        try:
            ipaddress.IPv6Address(source)
        except ipaddress.AddressValueError:
            address_family = socket.AF_INET
        else:
            address_family = socket.AF_INET6
        sock = socket.socket(address_family, socket.SOCK_STREAM)
        sock.bind((source, 0))
        sock.connect((hostname, port))
    callback = make_progressbar() if progressbar else None
    try:
        with SSHClient() as ssh:
            ssh.load_system_host_keys()
            if os.path.exists(KNOWN_HOSTS_FILE):
                ssh.load_host_keys(KNOWN_HOSTS_FILE)
            ssh.set_missing_host_key_policy(InteractivePolicy())
            ssh.connect(hostname, port, username, password, sock=sock)
            with ssh.open_sftp() as sftp:
                if mode == 'upload':
                    sftp.put(local_path, remote_path, callback=callback)
                elif mode == 'download':
                    sftp.get(remote_path, local_path, callback=callback)
                elif mode == 'size':
                    return sftp.stat(remote_path).st_size
    finally:
        if sock:
            sock.shutdown()
            sock.close()

def upload_sftp(*args, **kwargs):
    transfer_sftp('upload', *args, **kwargs)

def download_sftp(*args, **kwargs):
    transfer_sftp('download', *args, **kwargs)

def get_sftp_file_size(*args, **kwargs):
    return transfer_sftp('size', None, *args, **kwargs)


## TFTP routines
def upload_tftp(local_path, hostname, remote_path, port=69, source=None, progressbar=False):
    source_option = f'--interface {source}' if source else ''
    progress_flag = '--progress-bar' if progressbar else '-s'
    with open(local_path, 'rb') as file:
        cmd(f'curl {source_option} {progress_flag} -T - tftp://{hostname}:{port}/{remote_path}',\
            stderr=None, input=file.read()).encode()

def download_tftp(local_path, hostname, remote_path, port=69, source=None, progressbar=False):
    source_option = f'--interface {source}' if source else ''
    # Not really applicable but we pass it for the sake of uniformity.
    progress_flag = '--progress-bar' if progressbar else '-s'
    with open(local_path, 'wb') as file:
        file.write(cmd(f'curl {source_option} {progress_flag} tftp://{hostname}:{port}/{remote_path}',\
                       stderr=None).encode())

# get_tftp_file_size() is unimplemented because there is no way to obtain a file's size through TFTP,
#  as TFTP does not specify a SIZE command.


## HTTP(S) routines
def install_request_opener(urlstring, username, password):
    """
    Take `username` and `password` strings and install the appropriate
     password manager to `urllib.request.urlopen()` for the given `urlstring`.
    """
    manager = urlreq.HTTPPasswordMgrWithDefaultRealm()
    manager.add_password(None, urlstring, username, password)
    urlreq.install_opener(urlreq.build_opener(urlreq.HTTPBasicAuthHandler(manager)))

# upload_http() is unimplemented.

def download_http(local_path, urlstring, username=None, password=None, progressbar=False):
    """
    Download the file from from `urlstring` to `local_path`.
    Optionally takes `username` and `password` for authentication.
    """
    request = urlreq.Request(urlstring, headers={'User-Agent': 'VyOS/' + get_version()})
    if username:
        install_request_opener(urlstring, username, password)
    with open(local_path, 'wb') as file, urlreq.urlopen(request) as response:
        size = response.getheader('Content-Length')
        if progressbar and size:
            progress = make_incremental_progressbar(CHUNK_SIZE / int(size))
            next(progress)
            for chunk in iter(lambda: response.read(CHUNK_SIZE), b''):
                file.write(chunk)
                next(progress)
            next(progress)
        # If we can't determine the size or if a progress bar wasn't requested,
        #  we can let `shutil` take care of the copying.
        else:
            shutil.copyfileobj(response, file)

def get_http_file_size(urlstring, username=None, password=None):
    """
    Return the size of the file from `urlstring` in terms of number of bytes.
    Optionally takes `username` and `password` for authentication.
    """
    request = urlreq.Request(urlstring, headers={'User-Agent': 'VyOS/' + get_version()})
    if username:
        install_request_opener(urlstring, username, password)
    with urlreq.urlopen(request) as response:
        size = response.getheader('Content-Length')
        if size:
            return int(size)
        # The server didn't send 'Content-Length' in the response headers.
        else:
            raise ValueError('Failed to receive file size from HTTP server.')


## Dynamic dispatchers
def download(local_path, urlstring, source=None, progressbar=False):
    """
    Dispatch the appropriate download function for the given `urlstring` and save to `local_path`.
    Optionally takes a `source` address (not valid for HTTP(S)).
    Supports HTTP, HTTPS, FTP, SFTP, SCP (through SFTP) and TFTP.
    Reads `$REMOTE_USERNAME` and `$REMOTE_PASSWORD` environment variables.
    """
    url = urllib.parse.urlparse(urlstring)
    username, password = get_authentication_variables(url.username, url.password)
    port = get_port_from_url(url)

    if url.scheme == 'http' or url.scheme == 'https':
        if source:
            print_error('Warning: Custom source address not supported for HTTP connections.')
        download_http(local_path, urlstring, username, password, progressbar)
    elif url.scheme == 'ftp':
        username = username if username else 'anonymous'
        download_ftp(local_path, url.hostname, url.path, username, password, port, source, progressbar)
    elif url.scheme == 'sftp' or url.scheme == 'scp':
        download_sftp(local_path, url.hostname, url.path, username, password, port, source, progressbar)
    elif url.scheme == 'tftp':
        download_tftp(local_path, url.hostname, url.path, port, source, progressbar)
    else:
        raise ValueError(f'Unsupported URL scheme: {url.scheme}')

def upload(local_path, urlstring, source=None, progressbar=False):
    """
    Dispatch the appropriate upload function for the given URL and upload from local path.
    Optionally takes a `source` address.
    Supports FTP, SFTP, SCP (through SFTP) and TFTP.
    Reads `$REMOTE_USERNAME` and `$REMOTE_PASSWORD` environment variables.
    """
    url = urllib.parse.urlparse(urlstring)
    username, password = get_authentication_variables(url.username, url.password)
    port = get_port_from_url(url)

    if url.scheme == 'ftp':
        username = username if username else 'anonymous'
        upload_ftp(local_path, url.hostname, url.path, username, password, port, source, progressbar)
    elif url.scheme == 'sftp' or url.scheme == 'scp':
        upload_sftp(local_path, url.hostname, url.path, username, password, port, source, progressbar)
    elif url.scheme == 'tftp':
        upload_tftp(local_path, url.hostname, url.path, port, source, progressbar)
    else:
        raise ValueError(f'Unsupported URL scheme: {url.scheme}')

def get_remote_file_size(urlstring, source=None):
    """
    Dispatch the appropriate function to return the size of the remote file from `urlstring`
     in terms of number of bytes.
    Optionally takes a `source` address (not valid for HTTP(S)).
    Supports HTTP, HTTPS, FTP and SFTP (through SFTP).
    Reads `$REMOTE_USERNAME` and `$REMOTE_PASSWORD` environment variables.
    """
    url = urllib.parse.urlparse(urlstring)
    username, password = get_authentication_variables(url.username, url.password)
    port = get_port_from_url(url)

    if url.scheme == 'http' or url.scheme == 'https':
        return get_http_file_size(urlstring, username, password)
    elif url.scheme == 'ftp':
        username = username if username else 'anonymous'
        return get_ftp_file_size(url.hostname, url.path, username, password, port, source)
    elif url.scheme == 'sftp' or url.scheme == 'scp':
        return get_sftp_file_size(url.hostname, url.path, username, password, port, source)
    else:
        raise ValueError(f'Unsupported URL scheme: {url.scheme}')

def get_remote_config(urlstring, source=None):
    """
    Download remote (config) file from `urlstring` and return the contents as a string.
        Args:
            remote file URI:
                tftp://<host>[:<port>]/<file>
                http[s]://<host>[:<port>]/<file>
                [scp|sftp|ftp]://[<user>[:<passwd>]@]<host>[:port]/<file>
            source address (optional):
                <interface>
                <IP address>
    """
    temp = tempfile.NamedTemporaryFile(delete=False).name
    try:
        download(temp, urlstring, source)
        with open(temp, 'r') as file:
            return file.read()
    finally:
        os.remove(temp)

def friendly_download(local_path, urlstring, source=None):
    """
    Download from `urlstring` to `local_path` in an informative way.
    Checks the storage space before attempting download.
    Intended to be called from interactive, user-facing scripts.
    """
    destination_directory = os.path.dirname(local_path)
    try:
        free_space = shutil.disk_usage(destination_directory).free
        try:
            file_size = get_remote_file_size(urlstring, source)
            if file_size < 1024 * 1024:
                print_error(f'The file is {file_size / 1024.0:.3f} KiB.')
            else:
                print_error(f'The file is {file_size / (1024.0 * 1024.0):.3f} MiB.')
            if file_size > free_space:
                raise OSError(f'Not enough disk space available in "{destination_directory}".')
        except ValueError:
            # Can't do a storage check in this case, so we bravely continue.
            file_size = 0
            print_error('Could not determine the file size in advance.')
        else:
            print_error('Downloading...')
            download(local_path, urlstring, source, progressbar=file_size > 1024 * 1024)
    except KeyboardInterrupt:
        print_error('Download aborted by user.')
        sys.exit(1)
    except:
        import traceback
        # There are a myriad different reasons a download could fail.
        # SSH errors, FTP errors, I/O errors, HTTP errors (403, 404...)
        # We omit the scary stack trace but print the error nevertheless.
        print_error(f'Failed to download {urlstring}.')
        traceback.print_exception(*sys.exc_info()[:2], None)
        sys.exit(1)
    else:
        print_error('Download complete.')
