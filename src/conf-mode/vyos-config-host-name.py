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

from vyos.config import Config
from vyos.util import ConfigError

hostname_config = "/etc/hostname"
mailname_config = "/etc/mailname"
hostname_regex = re.compile("^[A-Za-z0-9][-.A-Za-z0-9]*[A-Za-z0-9]$")

def get_config():
    conf = Config()
    conf.set_level("system")
    
	hostname = conf.return_value("host-name")
	domain = conf.return_value("domain-name")

    return {
		"hostname": hostname,
		"domain": domain
	}

def verify(config):
	# check for invalid host
	
	# pattern $VAR(@) "^[[:alnum:]][-.[:alnum:]]*[[:alnum:]]$" ; "invalid host name $VAR(@)"
	valid = hostname_regex.match(config.hostname)
	if (!valid):
		raise ConfigError('invalid host name' + config.hostname)

	# pattern $VAR(@) "^.{1,63}$" ; "invalid host-name length"
	length = len(config.hostname)
	if length < 1 or length > 63:
		raise ConfigError('invalid host-name length')

	return None


def generate(config):
	mailname = config.hostname
	if config.domain != "":
		mailname += '.' + config.domain

	# update /etc/hostname
	with open(hostname_config, 'w') as f:
		f.write(config.hostname)

	# update /etc/mailname
	with open(mailname_config, 'w') as f:
		f.write(mailname)

	return None


def apply(config):
	# set hostname for the current session
    cmd = "hostname " + config.hostname
    os.system(cmd)

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
