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
import subprocess

import vyos.defaults
from vyos.config import Config
from vyos import ConfigError

vyos_conf_scripts_dir = vyos.defaults.directories['conf_mode']

dependencies = [
    'https.py',
]

def request_certbot(cert):
    email = cert.get('email')
    if email is not None:
        email_flag = '-m {0}'.format(email)
    else:
        email_flag = ''

    domains = cert.get('domains')
    if domains is not None:
        domain_flag = '-d ' + ' -d '.join(domains)
    else:
        domain_flag = ''

    certbot_cmd = 'certbot certonly -n --nginx --agree-tos --no-eff-email --expand {0} {1}'.format(email_flag, domain_flag)

    completed = subprocess.run(certbot_cmd, shell=True)

    return completed.returncode

def get_config():
    conf = Config()
    if not conf.exists('service https certificates certbot'):
        return None
    else:
        conf.set_level('service https certificates certbot')

    cert = {}

    if conf.exists('domain-name'):
        cert['domains'] = conf.return_values('domain-name')

    if conf.exists('email'):
        cert['email'] = conf.return_value('email')

    return cert

def verify(cert):
    if cert is None:
        return None

    if 'domains' not in cert:
        raise ConfigError("At least one domain name is required to"
                          " request a letsencrypt certificate.")

    if 'email' not in cert:
        raise ConfigError("An email address is required to request"
                          " a letsencrypt certificate.")

def generate(cert):
    if cert is None:
        return None

    # certbot will attempt to reload nginx, even with 'certonly';
    # start nginx if not active
    ret = os.system('systemctl is-active --quiet nginx.ervice')
    if ret:
        os.system('sudo systemctl start nginx.service')

    ret = request_certbot(cert)
    if ret:
        raise ConfigError("The certbot request failed for the"
                          " specified domains.")

def apply(cert):
    if cert is not None:
        os.system('sudo systemctl restart certbot.timer')
    else:
        os.system('sudo systemctl stop certbot.timer')
        return None

    for dep in dependencies:
        cmd = '{0}/{1}'.format(vyos_conf_scripts_dir, dep)
        try:
            subprocess.check_call(cmd, shell=True)
        except subprocess.CalledProcessError as err:
            raise ConfigError(str(err))

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)

