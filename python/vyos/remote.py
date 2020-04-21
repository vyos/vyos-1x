# Copyright 2019 VyOS maintainers and contributors <maintainers@vyos.io>
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

import sys
import os
import re
import fileinput

from vyos.util import cmd
from vyos.util import DEVNULL


def check_and_add_host_key(host_name):
    """
    Filter host keys and prompt for adding key to known_hosts file, if
    needed.
    """
    known_hosts = '{}/.ssh/known_hosts'.format(os.getenv('HOME'))
    if not os.path.exists(known_hosts):
        mode = 0o600
        os.mknod(known_hosts, 0o600)

    keyscan_cmd = 'ssh-keyscan -t rsa {}'.format(host_name)

    try:
        host_key = cmd(keyscan_cmd, stderr=DEVNULL)
    except OSError:
        sys.exit("Can not get RSA host key")

    # libssh2 (jessie; stretch) does not recognize ec host keys, and curl
    # will fail with error 51 if present in known_hosts file; limit to rsa.
    usable_keys = False
    offending_keys = []
    for line in fileinput.input(known_hosts, inplace=True):
        if host_name in line and 'ssh-rsa' in line:
            if line.split()[-1] != host_key.split()[-1]:
                offending_keys.append(line)
                continue
            else:
                usable_keys = True
        if host_name in line and not 'ssh-rsa' in line:
            continue

        sys.stdout.write(line)

    if usable_keys:
        return

    if offending_keys:
        print("Host key has changed!")
        print("If you trust the host key fingerprint below, continue.")

    fingerprint_cmd = 'ssh-keygen -lf /dev/stdin'
    try:
        fingerprint = cmd(fingerprint_cmd, stderr=DEVNULL, input=host_key)
    except OSError:
        sys.exit("Can not get RSA host key fingerprint.")

    print("RSA host key fingerprint is {}".format(fingerprint.split()[1]))
    response = input("Do you trust this host? [y]/n ")

    if not response or response == 'y':
        with open(known_hosts, 'a+') as f:
            print("Adding {} to the list of known"
                  " hosts.".format(host_name))
            f.write(host_key)
    else:
        sys.exit("Host not trusted")

def get_remote_config(remote_file):
    """ Invoke curl to download remote (config) file.

        Args:
            remote file URI:
                scp://<user>[:<passwd>]@<host>/<file>
                sftp://<user>[:<passwd>]@<host>/<file>
                http://<host>/<file>
                https://<host>/<file>
                ftp://<user>[:<passwd>]@<host>/<file>
                tftp://<host>/<file>
    """
    request = dict.fromkeys(['protocol', 'user', 'host', 'file'])
    protocols = ['scp', 'sftp', 'http', 'https', 'ftp', 'tftp']
    or_protocols = '|'.join(protocols)

    request_match = re.match(r'(' + or_protocols + r')://(.*?)(/.*)',
                             remote_file)
    if request_match:
        (request['protocol'], request['host'],
                request['file']) = request_match.groups()
    else:
        print("Malformed URI")
        sys.exit(1)

    user_match = re.search(r'(.*)@(.*)', request['host'])
    if user_match:
        request['user'] = user_match.groups()[0]
        request['host'] = user_match.groups()[1]

    remote_file = '{0}://{1}{2}'.format(request['protocol'], request['host'], request['file'])

    if request['protocol'] in ('scp', 'sftp'):
        check_and_add_host_key(request['host'])

    redirect_opt = ''

    if request['protocol'] in ('http', 'https'):
        redirect_opt = '-L'
        # Try header first, and look for 'OK' or 'Moved' codes:
        curl_cmd = 'curl {0} -q -I {1}'.format(redirect_opt, remote_file)
        try:
            curl_output = cmd(curl_cmd)
        except OSError:
            sys.exit(1)

        return_vals = re.findall(r'^HTTP\/\d+\.?\d\s+(\d+)\s+(.*)$',
                                 curl_output, re.MULTILINE)
        for val in return_vals:
            if int(val[0]) not in [200, 301, 302]:
                print('HTTP error: {0} {1}'.format(*val))
                sys.exit(1)

    if request['user']:
        curl_cmd = 'curl -# -u {0} {1}'.format(request['user'], remote_file)
    else:
        curl_cmd = 'curl {0} -# {1}'.format(redirect_opt, remote_file)

    try:
        return cmd(curl_cmd, stderr=None)
    except OSError:
        return None
