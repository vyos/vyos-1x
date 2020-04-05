#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
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
#
#

import sys
import os
import tempfile
import pathlib
import ssl

import vyos.defaults
from vyos.config import Config
from vyos import ConfigError
from vyos.util import cmd

vyos_conf_scripts_dir = vyos.defaults.directories['conf_mode']

# XXX: this model will need to be extended for tag nodes
dependencies = [
    'https.py',
]

def status_self_signed(cert_data):
# check existence and expiration date
    path = pathlib.Path(cert_data['conf'])
    if not path.is_file():
        return False
    path = pathlib.Path(cert_data['crt'])
    if not path.is_file():
        return False
    path = pathlib.Path(cert_data['key'])
    if not path.is_file():
        return False

    # check if certificate is 1/2 past lifetime, with openssl -checkend
    end_days = int(cert_data['lifetime'])
    end_seconds = int(0.5*60*60*24*end_days)
    checkend_cmd = 'openssl x509 -checkend {end} -noout -in {crt}'.format(end=end_seconds, **cert_data)
    try:
        cmd(checkend_cmd, message='Called process error')
        return True
    except OSError as err:
        if err.errno == 1:
            return False
        print(err)
        # XXX: This seems wrong to continue on failure
        # implicitely returning None

def generate_self_signed(cert_data):
    san_config = None

    if ssl.OPENSSL_VERSION_INFO < (1, 1, 1, 0, 0):
        san_config = tempfile.NamedTemporaryFile()
        with open(san_config.name, 'w') as fd:
            fd.write('[req]\n')
            fd.write('distinguished_name=req\n')
            fd.write('[san]\n')
            fd.write('subjectAltName=DNS:vyos\n')

        openssl_req_cmd = ('openssl req -x509 -nodes -days {lifetime} '
                           '-newkey rsa:4096 -keyout {key} -out {crt} '
                           '-subj "/O=Sentrium/OU=VyOS/CN=vyos" '
                           '-extensions san -config {san_conf}'
                           ''.format(san_conf=san_config.name,
                                     **cert_data))

    else:
        openssl_req_cmd = ('openssl req -x509 -nodes -days {lifetime} '
                           '-newkey rsa:4096 -keyout {key} -out {crt} '
                           '-subj "/O=Sentrium/OU=VyOS/CN=vyos" '
                           '-addext "subjectAltName=DNS:vyos"'
                           ''.format(**cert_data))

    try:
        cmd(openssl_req_cmd, message='Called process error')
    except OSError as err:
        print(err)
        # XXX: seems wrong to ignore the failure

    os.chmod('{key}'.format(**cert_data), 0o400)

    with open('{conf}'.format(**cert_data), 'w') as f:
        f.write('ssl_certificate {crt};\n'.format(**cert_data))
        f.write('ssl_certificate_key {key};\n'.format(**cert_data))

    if san_config:
        san_config.close()

def get_config():
    vyos_cert = vyos.defaults.vyos_cert_data

    conf = Config()
    if not conf.exists('service https certificates system-generated-certificate'):
        return None
    else:
        conf.set_level('service https certificates system-generated-certificate')

    if conf.exists('lifetime'):
        lifetime = conf.return_value('lifetime')
        vyos_cert['lifetime'] = lifetime

    return vyos_cert

def verify(vyos_cert):
    return None

def generate(vyos_cert):
    if vyos_cert is None:
        return None

    if not status_self_signed(vyos_cert):
        generate_self_signed(vyos_cert)

def apply(vyos_cert):
    for dep in dependencies:
        command = '{0}/{1}'.format(vyos_conf_scripts_dir, dep)
        cmd(command, raising=ConfigError)

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
