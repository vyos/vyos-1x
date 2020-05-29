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

import os

from sys import exit

from vyos.config import Config
from vyos.template import render
from vyos.util import call
from vyos import ConfigError

from vyos import airbag
airbag.enable()

config_file = r'/run/dhcp-relay/dhcp.conf'

default_config_data = {
    'interface': [],
    'server': [],
    'options': [],
    'hop_count': '10',
    'relay_agent_packets': 'forward'
}

def get_config():
    relay = default_config_data
    conf = Config()
    if not conf.exists(['service', 'dhcp-relay']):
        return None
    else:
        conf.set_level(['service', 'dhcp-relay'])

    # Network interfaces to listen on
    if conf.exists(['interface']):
        relay['interface'] = conf.return_values(['interface'])

    # Servers equal to the address of the DHCP server(s)
    if conf.exists(['server']):
        relay['server'] = conf.return_values(['server'])

    conf.set_level(['service', 'dhcp-relay', 'relay-options'])

    if conf.exists(['hop-count']):
        count = '-c ' + conf.return_value(['hop-count'])
        relay['options'].append(count)

    # Specify the maximum packet size to send to a DHCPv4/BOOTP server.
    # This might be done to allow sufficient space for addition of relay agent
    # options while still fitting into the Ethernet MTU size.
    #
    # Available in DHCPv4 mode only:
    if conf.exists(['max-size']):
        size = '-A ' + conf.return_value(['max-size'])
        relay['options'].append(size)

    # Control the handling of incoming DHCPv4 packets which already contain
    # relay agent options. If such a packet does not have giaddr set in its
    # header, the DHCP standard requires that the packet be discarded. However,
    # if giaddr is set, the relay agent may handle the situation in four ways:
    # It may append its own set of relay options to the packet, leaving the
    # supplied option field intact; it may replace the existing agent option
    # field; it may forward the packet unchanged; or, it may discard it.
    #
    # Available in DHCPv4 mode only:
    if conf.exists(['relay-agents-packets']):
        pkt = '-a -m ' + conf.return_value(['relay-agents-packets'])
        relay['options'].append(pkt)

    return relay

def verify(relay):
    # bail out early - looks like removal from running config
    if relay is None:
        return None

    if 'lo' in relay['interface']:
        raise ConfigError('DHCP relay does not support the loopback interface.')

    if len(relay['server']) == 0:
        raise ConfigError('No DHCP relay server(s) configured.\n' \
                          'At least one DHCP relay server required.')

    return None

def generate(relay):
    # bail out early - looks like removal from running config
    if not relay:
        return None

    render(config_file, 'dhcp-relay/config.tmpl', relay)
    return None

def apply(relay):
    if relay:
        call('systemctl restart isc-dhcp-relay.service')
    else:
        # DHCP relay support is removed in the commit
        call('systemctl stop isc-dhcp-relay.service')
        if os.path.exists(config_file):
            os.unlink(config_file)

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
