#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
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

import os
import re
import sys
import subprocess

from vyos.config import Config
from vyos.util import ConfigError

hostname_regex = re.compile("^[A-Za-z0-9][-.A-Za-z0-9]*[A-Za-z0-9]$")

def get_config():
    conf = Config()

    hostname = conf.return_value("system host-name")
    domain = conf.return_value("system domain-name")

    # No one likes fixups, but we really don't want VyOS fail to boot
    # if hostname is not in the config
    if not hostname:
        hostname = "vyos"

    if domain:
        fqdn = "{0}.{1}".format(hostname, domain)
    else:
        fqdn = hostname

    return {"hostname": hostname, "domain": domain, "fqdn": fqdn}

def verify(config):
    # check for invalid host
	
    # pattern $VAR(@) "^[[:alnum:]][-.[:alnum:]]*[[:alnum:]]$" ; "invalid host name $VAR(@)"
    if not hostname_regex.match(config["hostname"]):
        raise ConfigError('Invalid host name ' + config["hostname"])

    # pattern $VAR(@) "^.{1,63}$" ; "invalid host-name length"
    length = len(config["hostname"])
    if length < 1 or length > 63:
        raise ConfigError('Invalid host-name length, must be less than 63 characters')

    return None


def generate(config):
    # read the hosts file
    with open('/etc/hosts', 'r') as f:
        hosts = f.read()

    # get the current hostname
    old_hostname = subprocess.check_output(['hostname']).decode().strip()

    # replace the local host line
    hosts = re.sub(r"(127.0.1.1\s+{0}.*)".format(old_hostname), r"127.0.1.1\t{0} # VyOS entry\n".format(config["fqdn"]), hosts)

    with open('/etc/hosts', 'w') as f:
        f.write(hosts)

    return None


def apply(config):
    os.system("hostnamectl set-hostname {0}".format(config["fqdn"]))

    # restart services that use the hostname
    os.system("systemctl restart rsyslog.service")

    return None


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
