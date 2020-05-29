#!/usr/bin/env python3
#
# Copyright (C) 2018-2020 VyOS maintainers and contributors
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

"""
conf-mode script for 'system host-name' and 'system domain-name'.
"""

import os
import re
import sys
import copy
import glob
import argparse
import jinja2

import vyos.util
import vyos.hostsd_client

from vyos.config import Config
from vyos import ConfigError
from vyos.util import cmd, call, run, process_named_running

from vyos import airbag
airbag.enable()

default_config_data = {
    'hostname': 'vyos',
    'domain_name': '',
    'domain_search': [],
    'nameserver': [],
    'no_dhcp_ns': False
}

def get_config():
    conf = Config()
    hosts = copy.deepcopy(default_config_data)

    if conf.exists("system host-name"):
        hosts['hostname'] = conf.return_value("system host-name")
        # This may happen if the config is not loaded yet,
        # e.g. if run by cloud-init
        if not hosts['hostname']:
            hosts['hostname'] = default_config_data['hostname']

    if conf.exists("system domain-name"):
        hosts['domain_name'] = conf.return_value("system domain-name")
        hosts['domain_search'].append(hosts['domain_name'])

    for search in conf.return_values("system domain-search domain"):
        hosts['domain_search'].append(search)

    if conf.exists("system name-server"):
        hosts['nameserver'] = conf.return_values("system name-server")

    if conf.exists("system disable-dhcp-nameservers"):
        hosts['no_dhcp_ns'] = True

    # system static-host-mapping
    hosts['static_host_mapping'] = []

    if conf.exists('system static-host-mapping host-name'):
        for hn in conf.list_nodes('system static-host-mapping host-name'):
            mapping = {}
            mapping['host'] = hn
            mapping['address'] = conf.return_value('system static-host-mapping host-name {0} inet'.format(hn))
            mapping['aliases'] = conf.return_values('system static-host-mapping host-name {0} alias'.format(hn))
            hosts['static_host_mapping'].append(mapping)

    return hosts


def verify(config):
    if config is None:
        return None

    # pattern $VAR(@) "^[[:alnum:]][-.[:alnum:]]*[[:alnum:]]$" ; "invalid host name $VAR(@)"
    hostname_regex = re.compile("^[A-Za-z0-9][-.A-Za-z0-9]*[A-Za-z0-9]$")
    if not hostname_regex.match(config['hostname']):
        raise ConfigError('Invalid host name ' + config["hostname"])

    # pattern $VAR(@) "^.{1,63}$" ; "invalid host-name length"
    length = len(config['hostname'])
    if length < 1 or length > 63:
        raise ConfigError(
            'Invalid host-name length, must be less than 63 characters')

    # The search list is currently limited to six domains with a total of 256 characters.
    # https://linux.die.net/man/5/resolv.conf
    if len(config['domain_search']) > 6:
        raise ConfigError(
            'The search list is currently limited to six domains')

    tmp = ' '.join(config['domain_search'])
    if len(tmp) > 256:
        raise ConfigError(
            'The search list is currently limited to 256 characters')

    # static mappings alias hostname
    if config['static_host_mapping']:
        for m in config['static_host_mapping']:
            if not m['address']:
                raise ConfigError('IP address required for ' + m['host'])
            for a in m['aliases']:
                if not hostname_regex.match(a) and len(a) != 0:
                    raise ConfigError('Invalid alias \'{0}\' in mapping {1}'.format(a, m['host']))

    return None


def generate(config):
    pass

def apply(config):
    if config is None:
        return None

    ## Send the updated data to vyos-hostsd

    # vyos-hostsd uses "tags" to identify data sources
    tag = "static"

    try:
        client = vyos.hostsd_client.Client()

        # Check if disable-dhcp-nameservers is configured, and if yes - delete DNS servers added by DHCP
        if config['no_dhcp_ns']:
            client.delete_name_servers('dhcp-.+')

        client.set_host_name(config['hostname'], config['domain_name'], config['domain_search'])

        client.delete_name_servers(tag)
        client.add_name_servers(tag, config['nameserver'])

        client.delete_hosts(tag)
        client.add_hosts(tag, config['static_host_mapping'])
    except vyos.hostsd_client.VyOSHostsdError as e:
        raise ConfigError(str(e))

    ## Actually update the hostname -- vyos-hostsd doesn't do that

    # No domain name -- the Debian way.
    hostname_new = config['hostname']

    # rsyslog runs into a race condition at boot time with systemd
    # restart rsyslog only if the hostname changed.
    hostname_old = cmd('hostnamectl --static')
    call(f'hostnamectl set-hostname --static {hostname_new}')

    # Restart services that use the hostname
    if hostname_new != hostname_old:
        call("systemctl restart rsyslog.service")

    # If SNMP is running, restart it too
    if process_named_running('snmpd'):
        call('systemctl restart snmpd.service')

    # restart pdns if it is used - we check for the control dir to not raise
    # an exception on system startup
    #
    #   File "/usr/lib/python3/dist-packages/vyos/configsession.py", line 128, in __run_command
    #     raise ConfigSessionError(output)
    # vyos.configsession.ConfigSessionError: [ system domain-name vyos.io ]
    # Fatal: Unable to generate local temporary file in directory '/run/powerdns': No such file or directory
    if os.path.isdir('/run/powerdns'):
        ret = run('/usr/bin/rec_control --socket-dir=/run/powerdns ping')
        if ret == 0:
            call('systemctl restart pdns-recursor.service')

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
