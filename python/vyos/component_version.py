# Copyright 2022 VyOS maintainers and contributors <maintainers@vyos.io>
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

"""
Functions for reading/writing component versions.

The config file version string has the following form:

VyOS 1.3/1.4:

// Warning: Do not remove the following line.
// vyos-config-version: "broadcast-relay@1:cluster@1:config-management@1:conntrack@3:conntrack-sync@2:dhcp-relay@2:dhcp-server@6:dhcpv6-server@1:dns-forwarding@3:firewall@5:https@2:interfaces@22:ipoe-server@1:ipsec@5:isis@1:l2tp@3:lldp@1:mdns@1:nat@5:ntp@1:pppoe-server@5:pptp@2:qos@1:quagga@8:rpki@1:salt@1:snmp@2:ssh@2:sstp@3:system@21:vrrp@2:vyos-accel-ppp@2:wanloadbalance@3:webproxy@2:zone-policy@1"
// Release version: 1.3.0

VyOS 1.2:

/* Warning: Do not remove the following line. */
/* === vyatta-config-version: "broadcast-relay@1:cluster@1:config-management@1:conntrack-sync@1:conntrack@1:dhcp-relay@2:dhcp-server@5:dns-forwarding@1:firewall@5:ipsec@5:l2tp@1:mdns@1:nat@4:ntp@1:pppoe-server@2:pptp@1:qos@1:quagga@7:snmp@1:ssh@1:system@10:vrrp@2:wanloadbalance@3:webgui@1:webproxy@2:zone-policy@1" === */
/* Release version: 1.2.8 */

"""

import os
import re
import sys
import fileinput

from vyos.xml_ref import component_version
from vyos.version import get_version
from vyos.defaults import directories

DEFAULT_CONFIG_PATH = os.path.join(directories['config'], 'config.boot')

def from_string(string_line, vintage='vyos'):
    """
    Get component version dictionary from string.
    Return empty dictionary if string contains no config information
    or raise error if component version string malformed.
    """
    version_dict = {}

    if vintage == 'vyos':
        if re.match(r'// vyos-config-version:.+', string_line):
            if not re.match(r'// vyos-config-version:\s+"([\w,-]+@\d+:)+([\w,-]+@\d+)"\s*', string_line):
                raise ValueError(f"malformed configuration string: {string_line}")

            for pair in re.findall(r'([\w,-]+)@(\d+)', string_line):
                version_dict[pair[0]] = int(pair[1])

    elif vintage == 'vyatta':
        if re.match(r'/\* === vyatta-config-version:.+=== \*/$', string_line):
            if not re.match(r'/\* === vyatta-config-version:\s+"([\w,-]+@\d+:)+([\w,-]+@\d+)"\s+=== \*/$', string_line):
                raise ValueError(f"malformed configuration string: {string_line}")

            for pair in re.findall(r'([\w,-]+)@(\d+)', string_line):
                version_dict[pair[0]] = int(pair[1])
    else:
        raise ValueError("Unknown config string vintage")

    return version_dict

def from_file(config_file_name=DEFAULT_CONFIG_PATH, vintage='vyos'):
    """
    Get component version dictionary parsing config file line by line
    """
    with open(config_file_name, 'r') as f:
        for line_in_config in f:
            version_dict = from_string(line_in_config, vintage=vintage)
            if version_dict:
                return version_dict

    # no version information
    return {}

def from_system():
    """
    Get system component version dict.
    """
    return component_version()

def format_string(ver: dict) -> str:
    """
    Version dict to string.
    """
    keys = list(ver)
    keys.sort()
    l = []
    for k in keys:
        v = ver[k]
        l.append(f'{k}@{v}')
    sep = ':'
    return sep.join(l)

def version_footer(ver: dict, vintage='vyos') -> str:
    """
    Version footer as string.
    """
    ver_str = format_string(ver)
    release = get_version()
    if vintage == 'vyos':
        ret_str = (f'// Warning: Do not remove the following line.\n'
                +  f'// vyos-config-version: "{ver_str}"\n'
                +  f'// Release version: {release}\n')
    elif vintage == 'vyatta':
        ret_str = (f'/* Warning: Do not remove the following line. */\n'
                +  f'/* === vyatta-config-version: "{ver_str}" === */\n'
                +  f'/* Release version: {release} */\n')
    else:
        raise ValueError("Unknown config string vintage")

    return ret_str

def system_footer(vintage='vyos') -> str:
    """
    System version footer as string.
    """
    ver_d = from_system()
    return version_footer(ver_d, vintage=vintage)

def write_version_footer(ver: dict, file_name, vintage='vyos'):
    """
    Write version footer to file.
    """
    footer = version_footer(ver=ver, vintage=vintage)
    if file_name:
        with open(file_name, 'a') as f:
            f.write(footer)
    else:
        sys.stdout.write(footer)

def write_system_footer(file_name, vintage='vyos'):
    """
    Write system version footer to file.
    """
    ver_d = from_system()
    return write_version_footer(ver_d, file_name=file_name, vintage=vintage)

def remove_footer(file_name):
    """
    Remove old version footer.
    """
    for line in fileinput.input(file_name, inplace=True):
        if re.match(r'/\* Warning:.+ \*/$', line):
            continue
        if re.match(r'/\* === vyatta-config-version:.+=== \*/$', line):
            continue
        if re.match(r'/\* Release version:.+ \*/$', line):
            continue
        if re.match('// vyos-config-version:.+', line):
            continue
        if re.match('// Warning:.+', line):
            continue
        if re.match('// Release version:.+', line):
            continue
        sys.stdout.write(line)
