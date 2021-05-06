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
import socket
import sys
import tempfile
from ftplib import FTP
import urllib.parse
import urllib.request

from vyos.util import cmd
from vyos.version import get_version
from paramiko import SSHClient


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
def download_http(urlstring, local_path):
    request = urllib.request.Request(urlstring, headers={'User-Agent': 'VyOS/' + get_version()})
    with open(local_path, 'wb') as file:
        with urllib.request.urlopen(request) as response:
            file.write(response.read())

def get_http_file_size(urlstring):
    request = urllib.request.Request(urlstring, headers={'User-Agent': 'VyOS/' + get_version()})
    with urllib.request.urlopen(request) as response:
        size = response.getheader('Content-Length')
        if size:
            return int(size)
        # The server didn't send 'Content-Length' in the response headers.
        else:
            raise ValueError('Failed to receive file size from HTTP server.')

# Dynamic dispatchers
def download(local_path, urlstring, source=None):
    """
    Dispatch the appropriate download function for the given URL and save to local path.
    """
    url = urllib.parse.urlparse(urlstring)
    if url.scheme == 'http' or url.scheme == 'https':
        if source:
            print('Warning: Custom source address not supported for HTTP connections.', file=sys.stderr)
        download_http(urlstring, local_path)
    elif url.scheme == 'ftp':
        username = url.username if url.username else 'anonymous'
        download_ftp(local_path, url.hostname, url.path, username, url.password, source=source)
    elif url.scheme == 'sftp' or url.scheme == 'scp':
        download_sftp(local_path, url.hostname, url.path, url.username, url.password, source=source)
    elif url.scheme == 'tftp':
        download_tftp(local_path, url.hostname, url.path, source=source)
    else:
        raise ValueError(f'Unsupported URL scheme: {url.scheme}')

def upload(local_path, urlstring, source=None):
    """
    Dispatch the appropriate upload function for the given URL and upload from local path.
    """
    url = urllib.parse.urlparse(urlstring)
    if url.scheme == 'ftp':
        username = url.username if url.username else 'anonymous'
        upload_ftp(local_path, url.hostname, url.path, username, url.password, source=source)
    elif url.scheme == 'sftp' or url.scheme == 'scp':
        upload_sftp(local_path, url.hostname, url.path, url.username, url.password, source=source)
    elif url.scheme == 'tftp':
        upload_tftp(local_path, url.hostname, url.path, source=source)
    else:
        raise ValueError(f'Unsupported URL scheme: {url.scheme}')

def get_remote_file_size(urlstring, source=None):
    """
    Return the size of the remote file in bytes.
    """
    url = urllib.parse.urlparse(urlstring)
    if url.scheme == 'http' or url.scheme == 'https':
        return get_http_file_size(urlstring)
    elif url.scheme == 'ftp':
        username = url.username if url.username else 'anonymous'
        return get_ftp_file_size(url.hostname, url.path, username, url.password, source=source)
    elif url.scheme == 'sftp' or url.scheme == 'scp':
        return get_sftp_file_size(url.hostname, url.path, url.username, url.password, source=source)
    else:
        raise ValueError(f'Unsupported URL scheme: {url.scheme}')

def get_remote_config(urlstring, source=None):
    """
    Download remote (config) file and return the contents.
        Args:
            remote file URI:
                scp://<user>[:<passwd>]@<host>/<file>
                sftp://<user>[:<passwd>]@<host>/<file>
                http://<host>/<file>
                https://<host>/<file>
                ftp://[<user>[:<passwd>]@]<host>/<file>
                tftp://<host>/<file>
    """
    url = urllib.parse.urlparse(urlstring)
    temp = tempfile.NamedTemporaryFile(delete=False).name
    try:
        download(temp, urlstring, source)
        with open(temp, 'r') as file:
            return file.read()
    finally:
        os.remove(temp)
