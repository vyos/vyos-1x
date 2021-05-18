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
import os
import shutil
import socket
import sys
import tempfile
import urllib.parse
import urllib.request

from vyos.util import cmd, ask_yes_no
from vyos.version import get_version
from paramiko import SSHClient, SSHException, MissingHostKeyPolicy


known_hosts_file = os.path.expanduser('~/.ssh/known_hosts')

def print_error(str):
    """
    Used for warnings and out-of-band messages to avoid mangling precious
    stdout output.
    """
    sys.stderr.write(str)
    sys.stderr.write('\n')
    sys.stderr.flush()

class InteractivePolicy(MissingHostKeyPolicy):
    """
    Policy for interactively querying the user on whether to proceed with
    SSH connections to unknown hosts.
    """
    def missing_host_key(self, client, hostname, key):
        print_error(f"Host '{hostname}' not found in known hosts.")
        print_error('Fingerprint: ' + key.get_fingerprint().hex())
        if ask_yes_no('Do you wish to continue?'):
            if client._host_keys_filename and ask_yes_no('Do you wish to permanently add this host/key pair to known hosts?'):
                client._host_keys.add(hostname, key.get_name(), key)
                client.save_host_keys(client._host_keys_filename)
        else:
            raise SSHException(f"Cannot connect to unknown host '{hostname}'.")


## FTP routines
def transfer_ftp(mode, local_path, hostname, remote_path,\
                 username='anonymous', password='', port=21, source=None):
    with FTP(source_address=source) as conn:
        conn.connect(hostname, port)
        conn.login(username, password)
        if mode == 'upload':
            with open(local_path, 'rb') as file:
                conn.storbinary(f'STOR {remote_path}', file)
        elif mode == 'download':
            with open(local_path, 'wb') as file:
                conn.retrbinary(f'RETR {remote_path}', file.write)
        elif mode == 'size':
            size = conn.size(remote_path)
            if size:
                return size
            else:
                # SIZE is an extension to the FTP specification, although it's extremely common.
                raise ValueError('Failed to receive file size from FTP server. \
                Perhaps the server does not implement the SIZE command?')

def upload_ftp(*args, **kwargs):
    transfer_ftp('upload', *args, **kwargs)

def download_ftp(*args, **kwargs):
    transfer_ftp('download', *args, **kwargs)

def get_ftp_file_size(*args, **kwargs):
    return transfer_ftp('size', None, *args, **kwargs)


## SFTP/SCP routines
def transfer_sftp(mode, local_path, hostname, remote_path,\
                  username=None, password=None, port=22, source=None):
    sock = None
    if source:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((source, 0))
        sock.connect((hostname, port))
    try:
        with SSHClient() as ssh:
            ssh.load_system_host_keys()
            if os.path.exists(known_hosts_file):
                ssh.load_host_keys(known_hosts_file)
            ssh.set_missing_host_key_policy(InteractivePolicy())
            ssh.connect(hostname, port, username, password, sock=sock)
            with ssh.open_sftp() as sftp:
                if mode == 'upload':
                    sftp.put(local_path, remote_path)
                elif mode == 'download':
                    sftp.get(remote_path, local_path)
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
def upload_tftp(local_path, hostname, remote_path, port=69, source=None):
    source_option = f'--interface {source}' if source else ''
    with open(local_path, 'rb') as file:
        cmd(f'curl {source_option} -s -T - tftp://{hostname}:{port}/{remote_path}',\
            stderr=None, input=file.read()).encode()

def download_tftp(local_path, hostname, remote_path, port=69, source=None):
    source_option = f'--interface {source}' if source else ''
    with open(local_path, 'wb') as file:
        file.write(cmd(f'curl {source_option} -s tftp://{hostname}:{port}/{remote_path}',\
                       stderr=None).encode())

# get_tftp_file_size() is unimplemented because there is no way to obtain a file's size through TFTP,
# as TFTP does not specify a SIZE command.


## HTTP(S) routines
def install_request_opener(urlstring, username, password):
    """
    Take`username` and `password` strings and install the appropriate
    password manager to `urllib.request.urlopen()` for the given `urlstring`.
    """
    manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    manager.add_password(None, urlstring, username, password)
    urllib.request.install_opener(urllib.request.build_opener(manager))

# upload_http() is unimplemented.

def download_http(urlstring, local_path, username=None, password=None):
    """
    Download the file from from `urlstring` to `local_path`.
    Optionally takes `username` and `password` for authentication.
    """
    request = urllib.request.Request(urlstring, headers={'User-Agent': 'VyOS/' + get_version()})
    if username:
        install_request_opener(urlstring, username, password)
    with open(local_path, 'wb') as file:
        with urllib.request.urlopen(request) as response:
            file.write(response.read())

def get_http_file_size(urlstring, username=None, password=None):
    """
    Return the size of the file from `urlstring` in terms of number of bytes.
    Optionally takes `username` and `password` for authentication.
    """
    request = urllib.request.Request(urlstring, headers={'User-Agent': 'VyOS/' + get_version()})
    if username:
        install_request_opener(urlstring, username, password)
    with urllib.request.urlopen(request) as response:
        size = response.getheader('Content-Length')
        if size:
            return int(size)
        # The server didn't send 'Content-Length' in the response headers.
        else:
            raise ValueError('Failed to receive file size from HTTP server.')


# Dynamic dispatchers
def download(local_path, urlstring, authentication=None, source=None):
    """
    Dispatch the appropriate download function for the given `urlstring` and save to `local_path`.
    Optionally takes a `source` address (not valid for HTTP(S)) and an `authentication` tuple
     in the form of `(username, password)`.
    Supports HTTP, HTTPS, FTP, SFTP, SCP (through SFTP) and TFTP.
    """
    url = urllib.parse.urlparse(urlstring)
    if authentication:
        username, password = authentication
    else:
        username, password = url.username, url.password

    if url.scheme == 'http' or url.scheme == 'https':
        if source:
            print_error('Warning: Custom source address not supported for HTTP connections.')
        download_http(urlstring, local_path, username, password)
    elif url.scheme == 'ftp':
        username = username if username else 'anonymous'
        download_ftp(local_path, url.hostname, url.path, username, password, source=source)
    elif url.scheme == 'sftp' or url.scheme == 'scp':
        download_sftp(local_path, url.hostname, url.path, username, password, source=source)
    elif url.scheme == 'tftp':
        download_tftp(local_path, url.hostname, url.path, source=source)
    else:
        raise ValueError(f'Unsupported URL scheme: {url.scheme}')

def upload(local_path, urlstring, authentication=None, source=None):
    """
    Dispatch the appropriate upload function for the given URL and upload from local path.
    Optionally takes a `source` address and an `authentication` tuple
     in the form of `(username, password)`.
    `authentication` takes precedence over credentials in `urlstring`.
    Supports FTP, SFTP, SCP (through SFTP) and TFTP.
    """
    url = urllib.parse.urlparse(urlstring)
    if authentication:
        username, password = authentication
    else:
        username, password = url.username, url.password

    if url.scheme == 'ftp':
        username = username if username else 'anonymous'
        upload_ftp(local_path, url.hostname, url.path, username, password, source=source)
    elif url.scheme == 'sftp' or url.scheme == 'scp':
        upload_sftp(local_path, url.hostname, url.path, username, password, source=source)
    elif url.scheme == 'tftp':
        upload_tftp(local_path, url.hostname, url.path, source=source)
    else:
        raise ValueError(f'Unsupported URL scheme: {url.scheme}')

def get_remote_file_size(urlstring, authentication=None, source=None):
    """
    Dispatch the appropriate function to return the size of the remote file from `urlstring`
     in terms of number of bytes.
    Optionally takes a `source` address (not valid for HTTP(S)) and an `authentication` tuple
     in the form of `(username, password)`.
    `authentication` takes precedence over credentials in `urlstring`.
    Supports HTTP, HTTPS, FTP and SFTP (through SFTP).
    """
    url = urllib.parse.urlparse(urlstring)
    if authentication:
        username, password = authentication
    else:
        username, password = url.username, url.password

    if url.scheme == 'http' or url.scheme == 'https':
        return get_http_file_size(urlstring, authentication)
    elif url.scheme == 'ftp':
        username = username if username else 'anonymous'
        return get_ftp_file_size(url.hostname, url.path, username, password, source=source)
    elif url.scheme == 'sftp' or url.scheme == 'scp':
        return get_sftp_file_size(url.hostname, url.path, username, password, source=source)
    else:
        raise ValueError(f'Unsupported URL scheme: {url.scheme}')

def get_remote_config(urlstring, authentication=None, source=None):
    """
    Download remote (config) file from `urlstring` and return the contents as a string.
        Args:
            remote file URI:
                scp://<user>[:<passwd>]@<host>/<file>
                sftp://<user>[:<passwd>]@<host>/<file>
                http://<host>/<file>
                https://<host>/<file>
                ftp://[<user>[:<passwd>]@]<host>/<file>
                tftp://<host>/<file>
            authentication tuple (optional):
                (<username>, <password>)
            source address (optional):
                <interface>
                <IP address>
    """
    url = urllib.parse.urlparse(urlstring)
    temp = tempfile.NamedTemporaryFile(delete=False).name
    try:
        download(temp, urlstring, authentication, source)
        with open(temp, 'r') as file:
            return file.read()
    finally:
        os.remove(temp)

def friendly_download(local_path, urlstring, authentication=None, source=None):
    """
    Intended to be called from interactive, user-facing scripts.
    """
    destination_directory = os.path.dirname(local_path)
    free_space = shutil.disk_usage(destination_directory).free
    try:
        try:
            file_size = get_remote_file_size(urlstring, authentication, source)
            if file_size < 1024 * 1024:
                print_error(f'The file is {file_size / 1024.0:.3f} KiB.')
            else:
                print_error(f'The file is {file_size / (1024.0 * 1024.0):.3f} MiB.')
            if file_size > free_space:
                raise OSError(f'Not enough disk space available in "{destination_directory}".')
        except ValueError:
            print_error('Could not determine the file size in advance.')
        else:
            # TODO: Progress bar
            print_error('Downloading...')
            download(local_path, urlstring, authentication, source)
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
