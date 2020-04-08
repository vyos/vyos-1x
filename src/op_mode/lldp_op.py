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


import argparse
import jinja2

from xml.dom import minidom
from sys import exit
from tabulate import tabulate

from vyos.util import popen
from vyos.config import Config

parser = argparse.ArgumentParser()
parser.add_argument("-a", "--all", action="store_true", help="Show LLDP neighbors on all interfaces")
parser.add_argument("-i", "--interface", action="store", help="Show LLDP neighbors on specific interface")

# Please be careful if you edit the template.
lldp_out = """Capability Codes: R - Router, B - Bridge, W - Wlan r - Repeater, S - Station
                  D - Docsis, T - Telephone, O - Other

Device ID                 Local     Proto  Cap   Platform             Port ID
---------                 -----     -----  ---   --------             -------
{% for n in neighbors -%}
{{ "%-25s" | format(n.chassis) }} {{ "%-9s" | format(n.interface) }} {{ "%-6s" | format(n.proto) }} {{ "%-5s" | format(n.cap) }} {{ "%-20s" | format(n.platform) }} {{ n.port }}
{% endfor -%}
"""

def _get_neighbors():
    command = '/usr/sbin/lldpcli -f xml show neighbors'
    out,_ = popen(command)
    return out

def extract_neighbor(neighbor):
    """
    Extract LLDP neighbor information from XML document passed as param neighbor

    <lldp>
     <interface label="Interface" name="eth0" via="LLDP" rid="3" age="0 day, 00:17:42">
      <chassis label="Chassis">
       <id label="ChassisID" type="mac">00:50:56:9d:a6:11</id>
       <name label="SysName">VyOS</name>
       <descr label="SysDescr">VyOS unknown</descr>
       <mgmt-ip label="MgmtIP">172.18.254.203</mgmt-ip>
       <mgmt-ip label="MgmtIP">fe80::250:56ff:fe9d:a611</mgmt-ip>
       <capability label="Capability" type="Bridge" enabled="off"/>
       <capability label="Capability" type="Router" enabled="on"/>
       <capability label="Capability" type="Wlan" enabled="off"/>
       <capability label="Capability" type="Station" enabled="off"/>
      </chassis>
      <port label="Port">
       <id label="PortID" type="mac">00:50:56:9d:a6:11</id>
       <descr label="PortDescr">eth0</descr>
       <ttl label="TTL">120</ttl>
       <auto-negotiation label="PMD autoneg" supported="no" enabled="no">
        <current label="MAU oper type">10GigBaseCX4 - X copper over 8 pair 100-Ohm balanced cable</current>
       </auto-negotiation>
      </port>
      <vlan label="VLAN" vlan-id="203">eth0.203</vlan>
      <lldp-med label="LLDP-MED">
       <device-type label="Device Type">Network Connectivity Device</device-type>
       <capability label="Capability" type="Capabilities" available="yes"/>
       <capability label="Capability" type="Policy" available="yes"/>
       <capability label="Capability" type="Location" available="yes"/>
       <capability label="Capability" type="MDI/PSE" available="yes"/>
       <capability label="Capability" type="MDI/PD" available="yes"/>
       <capability label="Capability" type="Inventory" available="yes"/>
       <inventory label="Inventory">
        <hardware label="Hardware Revision">None</hardware>
        <software label="Software Revision">4.19.54-amd64-vyos</software>
        <firmware label="Firmware Revision">6.00</firmware>
        <serial label="Serial Number">VMware-42 1d cf 87 ab 7f da 7e-3</serial>
        <manufacturer label="Manufacturer">VMware, Inc.</manufacturer>
        <model label="Model">VMware Virtual Platform</model>
        <asset label="Asset ID">No Asset Tag</asset>
       </inventory>
      </lldp-med>
     </interface>
    </lldp>
    """

    device = {
        'interface' : neighbor.getAttribute('name'),
        'chassis' : '',
        'proto' : neighbor.getAttribute('via'),
        'descr' : '',
        'cap' : '',
        'platform' : '',
        'port' : ''
    }

    # first change to <chassis> node and then retrieve <name> and <descr>
    chassis = neighbor.getElementsByTagName('chassis')
    device['chassis'] = chassis[0].getElementsByTagName('name')[0].firstChild.data
    # Cisco IOS comes with a ',' remove character ....
    device['platform'] = chassis[0].getElementsByTagName('descr')[0].firstChild.data[:20].replace(',',' ')

    # extract capabilities
    for capability in chassis[0].getElementsByTagName('capability'):
        # we are only interested in enabled capabilities ...
        if capability.getAttribute('enabled') == "on":
            if capability.getAttribute('type') == "Router":
                device['cap'] += 'R'
            elif capability.getAttribute('type') == "Bridge":
                device['cap'] += 'B'
            elif capability.getAttribute('type') == "Wlan":
                device['cap'] += 'W'
            elif capability.getAttribute('type') == "Station":
                device['cap'] += 'S'
            elif capability.getAttribute('type') == "Repeater":
                device['cap'] += 'r'
            elif capability.getAttribute('type') == "Telephone":
                device['cap'] += 'T'
            elif capability.getAttribute('type') == "Docsis":
                device['cap'] += 'D'
            elif capability.getAttribute('type') == "Other":
                device['cap'] += 'O'

    # first change to <port> node and then retrieve <descr>
    port = neighbor.getElementsByTagName('port')
    port = port[0].getElementsByTagName('descr')[0].firstChild.data
    device['port'] = port


    return device

if __name__ == '__main__':
    args = parser.parse_args()
    tmp = { 'neighbors' : [] }

    c = Config()
    if not c.exists_effective(['service', 'lldp']):
        print('Service LLDP is not configured')
        exit(0)

    if args.all:
       neighbors = minidom.parseString(_get_neighbors())
       for neighbor in neighbors.getElementsByTagName('interface'):
           tmp['neighbors'].append( extract_neighbor(neighbor) )

    elif args.interface:
        neighbors = minidom.parseString(_get_neighbors())
        for neighbor in neighbors.getElementsByTagName('interface'):
            # check if neighbor appeared on proper interface
            if neighbor.getAttribute('name') == args.interface:
                tmp['neighbors'].append( extract_neighbor(neighbor) )

    else:
        parser.print_help()
        exit(1)

    tmpl = jinja2.Template(lldp_out)
    config_text = tmpl.render(tmp)
    print(config_text)

    exit(0)
