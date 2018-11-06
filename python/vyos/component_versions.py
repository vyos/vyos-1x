# Copyright 2017 VyOS maintainers and contributors <maintainers@vyos.io>
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
The version data looks like:

/* Warning: Do not remove the following line. */
/* === vyatta-config-version:
"cluster@1:config-management@1:conntrack-sync@1:conntrack@1:dhcp-relay@1:dhcp-server@4:firewall@5:ipsec@4:nat@4:qos@1:quagga@2:system@8:vrrp@1:wanloadbalance@3:webgui@1:webproxy@1:zone-policy@1"
=== */
/* Release version: 1.2.0-rolling+201806131737 */
"""

import re

def get_component_version(string_line):
    """
    Get component version dictionary from string
    return empty dictionary if string contains no config information
    or raise error if component version string malformed
    """
    return_value = {}
    if re.match(r'/\* === vyatta-config-version:.+=== \*/$', string_line):

        if not re.match(r'/\* === vyatta-config-version:\s+"([\w,-]+@\d+:)+([\w,-]+@\d+)"\s+=== \*/$', string_line):
            raise ValueError("malformed configuration string: " + str(string_line))

        for pair in re.findall(r'([\w,-]+)@(\d+)', string_line):
            if pair[0] in return_value.keys():
                raise ValueError("duplicate unit name: \"" + str(pair[0]) + "\" in string: \"" + string_line + "\"")
            return_value[pair[0]] = int(pair[1])

    return return_value


def get_component_versions_from_file(config_file_name='/opt/vyatta/etc/config/config.boot'):
    """
    Get component version dictionary parsing config file line by line
    """
    f = open(config_file_name, 'r')
    for line_in_config in f:
        component_version = return_version(line_in_config)
        if component_version:
            return component_version
    raise ValueError("no config string in file:", config_file_name)
