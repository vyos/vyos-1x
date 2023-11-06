#!/usr/bin/python3

# Copyright 2021-2023 VyOS maintainers and contributors <maintainers@vyos.io>
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

import argparse
import re
import sys

from netaddr import IPNetwork, AddrFormatError

parser = argparse.ArgumentParser(description='strip off private information from VyOS config')

strictness = parser.add_mutually_exclusive_group()
strictness.add_argument('--loose', action='store_true', help='remove only information specified as arguments')
strictness.add_argument('--strict', action='store_true', help='remove any private information (implies all arguments below). This is the default behavior.')

parser.add_argument('--mac', action='store_true', help='strip off MAC addresses')
parser.add_argument('--hostname', action='store_true', help='strip off system host and domain names')
parser.add_argument('--username', action='store_true', help='strip off user names')
parser.add_argument('--dhcp', action='store_true', help='strip off DHCP shared network and static mapping names')
parser.add_argument('--domain', action='store_true', help='strip off domain names')
parser.add_argument('--asn', action='store_true', help='strip off BGP ASNs')
parser.add_argument('--snmp', action='store_true', help='strip off SNMP location information')
parser.add_argument('--lldp', action='store_true', help='strip off LLDP location information')

address_preserval = parser.add_mutually_exclusive_group()
address_preserval.add_argument('--address', action='store_true', help='strip off all IPv4 and IPv6 addresses')
address_preserval.add_argument('--public-address', action='store_true', help='only strip off public IPv4 and IPv6 addresses')
address_preserval.add_argument('--keep-address', action='store_true', help='preserve all IPv4 and IPv6 addresses')

# Censor the first half of the address.
ipv4_re = re.compile(r'(\d{1,3}\.){2}(\d{1,3}\.\d{1,3})')
ipv4_subst = r'xxx.xxx.\2'

# Censor all but the first two fields.
ipv6_re = re.compile(r'([0-9a-fA-F]{1,4}\:){2}([0-9a-fA-F:]+)')
ipv6_subst = r'xxxx:xxxx:\2'

def ip_match(match: re.Match, subst: str) -> str:
    """
    Take a Match and a substitution pattern, check if the match contains a valid IP address, strip
    information if it is. This routine is intended to be passed to `re.sub' as a replacement pattern.
    """
    result = match.group(0)
    # Is this a valid IP address?
    try:
        addr = IPNetwork(result).ip
    # No? Then we've got nothing to do with it.
    except AddrFormatError:
        return result
    # Should we strip it?
    if args.address or (args.public_address and not addr.is_private()):
        return match.expand(subst)
    # No? Then we'll leave it as is.
    else:
        return result

def strip_address(line: str) -> str:
    """
    Strip IPv4 and IPv6 addresses from the given string.
    """
    return ipv4_re.sub(lambda match: ip_match(match, ipv4_subst), ipv6_re.sub(lambda match: ip_match(match, ipv6_subst), line))

def strip_lines(rules: tuple) -> None:
    """
    Read stdin line by line and apply the given stripping rules.
    """
    try:
        for line in sys.stdin:
            if not args.keep_address:
                line = strip_address(line)
            for (condition, regexp, subst) in rules:
                if condition:
                    line = regexp.sub(subst, line)
            print(line, end='')
    # stdin can be cut for any reason, such as user interrupt or the pager terminating before the text can be read.
    # All we can do is gracefully exit.
    except (BrokenPipeError, EOFError, KeyboardInterrupt):
        sys.exit(1)

if __name__ == "__main__":
    args = parser.parse_args()
    # Strict mode is the default and the absence of loose mode implies presence of strict mode.
    if not args.loose:
        args.mac = args.domain = args.hostname = args.username = args.dhcp = args.asn = args.snmp = args.lldp = True
        if not args.public_address and not args.keep_address:
            args.address = True
    elif not args.address and not args.public_address:
        args.keep_address = True

    # (condition, precompiled regexp, substitution string)
    stripping_rules = [
        # Strip passwords
        (True, re.compile(r'password \S+'), 'password xxxxxx'),
        (True, re.compile(r'cisco-authentication \S+'), 'cisco-authentication xxxxxx'),
        # Strip public key information
        (True, re.compile(r'public-keys \S+'), 'public-keys xxxx@xxx.xxx'),
        (True, re.compile(r'type \'ssh-(rsa|dss)\''), 'type ssh-xxx'),
        (True, re.compile(r' key \S+'), ' key xxxxxx'),
        # Strip bucket
        (True, re.compile(r' bucket \S+'), ' bucket xxxxxx'),
        # Strip tokens
        (True, re.compile(r' token \S+'), ' token xxxxxx'),
        # Strip OpenVPN secrets
        (True, re.compile(r'(shared-secret-key-file|ca-cert-file|cert-file|dh-file|key-file|client) (\S+)'), r'\1 xxxxxx'),
        # Strip IPSEC secrets
        (True, re.compile(r'pre-shared-secret \S+'), 'pre-shared-secret xxxxxx'),
        (True, re.compile(r'secret \S+'), 'secret xxxxxx'),
        # Strip OSPF md5-key
        (True, re.compile(r'md5-key \S+'), 'md5-key xxxxxx'),
        # Strip WireGuard private-key
        (True, re.compile(r'private-key \S+'), 'private-key xxxxxx'),

        # Strip MAC addresses
        (args.mac, re.compile(r'([0-9a-fA-F]{2}\:){5}([0-9a-fA-F]{2}((\:{0,1})){3})'), r'xx:xx:xx:xx:xx:\2'),

        # Strip host-name, domain-name, domain-search and url
        (args.hostname, re.compile(r'(host-name|domain-name|domain-search|url) \S+'), r'\1 xxxxxx'),

        # Strip user-names
        (args.username, re.compile(r'(user|username|user-id) \S+'), r'\1 xxxxxx'),
        # Strip full-name
        (args.username, re.compile(r'(full-name) [ -_A-Z a-z]+'), r'\1 xxxxxx'),

        # Strip DHCP static-mapping and shared network names
        (args.dhcp, re.compile(r'(shared-network-name|static-mapping) \S+'), r'\1 xxxxxx'),

        # Strip host/domain names
        (args.domain, re.compile(r' (peer|remote-host|local-host|server) ([\w-]+\.)+[\w-]+'), r' \1 xxxxx.tld'),

        # Strip BGP ASNs
        (args.asn, re.compile(r'(bgp|remote-as) (\d+)'), r'\1 XXXXXX'),

        # Strip LLDP location parameters
        (args.lldp, re.compile(r'(altitude|datum|latitude|longitude|ca-value|country-code) (\S+)'), r'\1 xxxxxx'),

        # Strip SNMP location
        (args.snmp, re.compile(r'(location) \S+'), r'\1 xxxxxx'),
    ]
    strip_lines(stripping_rules)
