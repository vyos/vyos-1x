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
import sys
import tempfile
from ftplib import FTP
import urllib.parse
import urllib.request

from vyos.util import cmd
from paramiko import SSHClient

def upload_ftp(local_path, hostname, remote_path,\
               username='anonymous', password='', port=21):
    with open(local_path, 'rb') as file:
        with FTP() as conn:
            conn.connect(hostname, port)
            conn.login(username, password)
            conn.storbinary(f'STOR {remote_path}', file)

def download_ftp(local_path, hostname, remote_path,\
                 username='anonymous', password='', port=21):
    with open(local_path, 'wb') as file:
        with FTP() as conn:
            conn.connect(hostname, port)
            conn.login(username, password)
            conn.retrbinary(f'RETR {remote_path}', file.write)

def upload_sftp(local_path, hostname, remote_path,\
                username=None, password=None, port=22):
    with SSHClient() as ssh:
        ssh.load_system_host_keys()
        ssh.connect(hostname, port, username, password)
        with ssh.open_sftp() as sftp:
            sftp.put(local_path, remote_path)

def download_sftp(local_path, hostname, remote_path,\
                  username=None, password=None, port=22):
    with SSHClient() as ssh:
        ssh.load_system_host_keys()
        ssh.connect(hostname, port, username, password)
        with ssh.open_sftp() as sftp:
            sftp.get(remote_path, local_path)

def upload_tftp(local_path, hostname, remote_path, port=69):
    with open(local_path, 'rb') as file:
        cmd(f'curl -s -T - tftp://{hostname}:{port}/{remote_path}', stderr=None, input=file.read()).encode()

def download_tftp(local_path, hostname, remote_path, port=69):
    with open(local_path, 'wb') as file:
        file.write(cmd(f'curl -s tftp://{hostname}:{port}/{remote_path}', stderr=None).encode())

def download_http(urlstring, local_path):
    with open(local_path, 'wb') as file:
        with urllib.request.urlopen(urlstring) as response:
            file.write(response.read())

def download(local_path, urlstring):
    """
    Dispatch the appropriate download function for the given URL and save to local path.
    """
    url = urllib.parse.urlparse(urlstring)
    if url.scheme == 'http' or url.scheme == 'https':
        download_http(urlstring, local_path)
    elif url.scheme == 'ftp':
        username = url.username if url.username else 'anonymous'
        download_ftp(local_path, url.hostname, url.path, username, url.password)
    elif url.scheme == 'sftp' or url.scheme == 'scp':
        download_sftp(local_path, url.hostname, url.path, url.username, url.password)
    elif url.scheme == 'tftp':
        download_tftp(local_path, url.hostname, url.path)
    else:
        ValueError(f'Unsupported URL scheme: {url.scheme}')

def upload(local_path, urlstring):
    """
    Dispatch the appropriate upload function for the given URL and upload from local path.
    """
    url = urllib.parse.urlparse(urlstring)
    if url.scheme == 'ftp':
        username = url.username if url.username else 'anonymous'
        upload_ftp(local_path, url.hostname, url.path, username, url.password)
    elif url.scheme == 'sftp' or url.scheme == 'scp':
        upload_sftp(local_path, url.hostname, url.path, url.username, url.password)
    elif url.scheme == 'tftp':
        upload_tftp(local_path, url.hostname, url.path)
    else:
        ValueError(f'Unsupported URL scheme: {url.scheme}')

def get_remote_config(urlstring):
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
        download(temp, urlstring)
        with open(temp, 'r') as file:
            return file.read()
    finally:
        os.remove(temp)
