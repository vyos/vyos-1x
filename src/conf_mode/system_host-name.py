#!/usr/bin/env python3
#
# Copyright (C) 2018-2024 VyOS maintainers and contributors
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

import re
import sys
import copy

import vyos.hostsd_client

from vyos.base import Warning
from vyos.config import Config
from vyos.configdict import leaf_node_changed
from vyos.ifconfig import Section
from vyos.template import is_ip
from vyos.utils.process import cmd
from vyos.utils.process import call
from vyos.utils.process import process_named_running
from vyos import ConfigError
from vyos import airbag
airbag.enable()

default_config_data = {
    'hostname': 'vyos',
    'domain_name': '',
    'domain_search': [],
    'nameserver': [],
    'nameservers_dhcp_interfaces': {},
    'snmpd_restart_reqired': False,
    'static_host_mapping': {}
}

hostsd_tag = 'system'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    hosts = copy.deepcopy(default_config_data)

    hosts['hostname'] = conf.return_value(['system', 'host-name'])

    base = ['system']
    if leaf_node_changed(conf, base + ['host-name']) or leaf_node_changed(conf, base + ['domain-name']):
        hosts['snmpd_restart_reqired'] = True

    # This may happen if the config is not loaded yet,
    # e.g. if run by cloud-init
    if not hosts['hostname']:
        hosts['hostname'] = default_config_data['hostname']

    if conf.exists(['system', 'domain-name']):
        hosts['domain_name'] = conf.return_value(['system', 'domain-name'])
        hosts['domain_search'].append(hosts['domain_name'])

    if conf.exists(['system', 'domain-search']):
        for search in conf.return_values(['system', 'domain-search']):
            hosts['domain_search'].append(search)

    if conf.exists(['system', 'name-server']):
        for ns in conf.return_values(['system', 'name-server']):
            if is_ip(ns):
                hosts['nameserver'].append(ns)
            else:
                tmp = ''
                config_path = Section.get_config_path(ns)
                if conf.exists(['interfaces', config_path, 'address']):
                    tmp = conf.return_values(['interfaces', config_path, 'address'])

                hosts['nameservers_dhcp_interfaces'].update({ ns : tmp })

    # system static-host-mapping
    for hn in conf.list_nodes(['system', 'static-host-mapping', 'host-name']):
        hosts['static_host_mapping'][hn] = {}
        hosts['static_host_mapping'][hn]['address'] = conf.return_values(['system', 'static-host-mapping', 'host-name', hn, 'inet'])
        hosts['static_host_mapping'][hn]['aliases'] = conf.return_values(['system', 'static-host-mapping', 'host-name', hn, 'alias'])

    return hosts


def verify(hosts):
    if hosts is None:
        return None

    # pattern $VAR(@) "^[[:alnum:]][-.[:alnum:]]*[[:alnum:]]$" ; "invalid host name $VAR(@)"
    hostname_regex = re.compile("^[A-Za-z0-9][-.A-Za-z0-9]*[A-Za-z0-9]$")
    if not hostname_regex.match(hosts['hostname']):
        raise ConfigError('Invalid host name ' + hosts["hostname"])

    # pattern $VAR(@) "^.{1,63}$" ; "invalid host-name length"
    length = len(hosts['hostname'])
    if length < 1 or length > 63:
        raise ConfigError(
            'Invalid host-name length, must be less than 63 characters')

    all_static_host_mapping_addresses = []
    # static mappings alias hostname
    for host, hostprops in hosts['static_host_mapping'].items():
        if not hostprops['address']:
            raise ConfigError(f'IP address required for static-host-mapping "{host}"')
        all_static_host_mapping_addresses.append(hostprops['address'])
        for a in hostprops['aliases']:
            if not hostname_regex.match(a) and len(a) != 0:
                raise ConfigError(f'Invalid alias "{a}" in static-host-mapping "{host}"')

    for interface, interface_config in hosts['nameservers_dhcp_interfaces'].items():
        # Warnin user if interface does not have DHCP or DHCPv6 configured
        if not set(interface_config).intersection(['dhcp', 'dhcpv6']):
            Warning(f'"{interface}" is not a DHCP interface but uses DHCP name-server option!')

    return None


def generate(config):
    pass

def apply(config):
    if config is None:
        return None

    ## Send the updated data to vyos-hostsd
    try:
        hc = vyos.hostsd_client.Client()

        hc.set_host_name(config['hostname'], config['domain_name'])

        hc.delete_search_domains([hostsd_tag])
        if config['domain_search']:
            hc.add_search_domains({hostsd_tag: config['domain_search']})

        hc.delete_name_servers([hostsd_tag])
        if config['nameserver']:
            hc.add_name_servers({hostsd_tag: config['nameserver']})

        # add our own tag's (system) nameservers and search to resolv.conf
        hc.delete_name_server_tags_system(hc.get_name_server_tags_system())
        hc.add_name_server_tags_system([hostsd_tag])

        # this will add the dhcp client nameservers to resolv.conf
        for intf in config['nameservers_dhcp_interfaces']:
            hc.add_name_server_tags_system([f'dhcp-{intf}', f'dhcpv6-{intf}'])

        hc.delete_hosts([hostsd_tag])
        if config['static_host_mapping']:
            hc.add_hosts({hostsd_tag: config['static_host_mapping']})

        hc.apply()
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
    if process_named_running('snmpd') and config['snmpd_restart_reqired']:
        call('systemctl restart snmpd.service')

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
