# Copyright 2019-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

import functools
import os

from jinja2 import Environment
from jinja2 import FileSystemLoader
from jinja2 import ChainableUndefined
from vyos.defaults import directories
from vyos.utils.dict import dict_search_args
from vyos.utils.file import makedir
from vyos.utils.permission import chmod
from vyos.utils.permission import chown

# We use a mutable global variable for the default template directory
# to make it possible to call scripts from this repository
# outside of live VyOS systems.
# If something (like the image build scripts)
# want to call a script, they can modify the default location
# to the repository path.
DEFAULT_TEMPLATE_DIR = directories["templates"]

# Holds template filters registered via register_filter()
_FILTERS = {}
_TESTS = {}

# reuse Environments with identical settings to improve performance
@functools.lru_cache(maxsize=2)
def _get_environment(location=None):
    from os import getenv

    if location is None:
        loc_loader=FileSystemLoader(DEFAULT_TEMPLATE_DIR)
    else:
        loc_loader=FileSystemLoader(location)
    env = Environment(
        # Don't check if template files were modified upon re-rendering
        auto_reload=False,
        # Cache up to this number of templates for quick re-rendering
        cache_size=100,
        loader=loc_loader,
        trim_blocks=True,
        undefined=ChainableUndefined,
        extensions=['jinja2.ext.loopcontrols']
    )
    env.filters.update(_FILTERS)
    env.tests.update(_TESTS)
    return env


def register_filter(name, func=None):
    """Register a function to be available as filter in templates under given name.

    It can also be used as a decorator, see below in this module for examples.

    :raise RuntimeError:
        when trying to register a filter after a template has been rendered already
    :raise ValueError: when trying to register a name which was taken already
    """
    if func is None:
        return functools.partial(register_filter, name)
    if _get_environment.cache_info().currsize:
        raise RuntimeError(
            "Filters can only be registered before rendering the first template"
        )
    if name in _FILTERS:
        raise ValueError(f"A filter with name {name!r} was registered already")
    _FILTERS[name] = func
    return func

def register_test(name, func=None):
    """Register a function to be available as test in templates under given name.

    It can also be used as a decorator, see below in this module for examples.

    :raise RuntimeError:
        when trying to register a test after a template has been rendered already
    :raise ValueError: when trying to register a name which was taken already
    """
    if func is None:
        return functools.partial(register_test, name)
    if _get_environment.cache_info().currsize:
        raise RuntimeError(
            "Tests can only be registered before rendering the first template"
            )
    if name in _TESTS:
        raise ValueError(f"A test with name {name!r} was registered already")
    _TESTS[name] = func
    return func


def render_to_string(template, content, formater=None, location=None):
    """Render a template from the template directory, raise on any errors.

    :param template: the path to the template relative to the template folder
    :param content: the dictionary of variables to put into rendering context
    :param formater:
        if given, it has to be a callable the rendered string is passed through

    The parsed template files are cached, so rendering the same file multiple times
    does not cause as too much overhead.
    If used everywhere, it could be changed to load the template from Python
    environment variables from an importable Python module generated when the Debian
    package is build (recovering the load time and overhead caused by having the
    file out of the code).
    """
    template = _get_environment(location).get_template(template)
    rendered = template.render(content)
    if formater is not None:
        rendered = formater(rendered)
    return rendered


def render(
    destination,
    template,
    content,
    formater=None,
    permission=None,
    user=None,
    group=None,
    location=None,
):
    """Render a template from the template directory to a file, raise on any errors.

    :param destination: path to the file to save the rendered template in
    :param permission: permission bitmask to set for the output file
    :param user: user to own the output file
    :param group: group to own the output file

    All other parameters are as for :func:`render_to_string`.
    """
    # Create the directory if it does not exist
    folder = os.path.dirname(destination)
    makedir(folder, user, group)

    # As we are opening the file with 'w', we are performing the rendering before
    # calling open() to not accidentally erase the file if rendering fails
    rendered = render_to_string(template, content, formater, location)

    # Write to file
    with open(destination, "w") as file:
        chmod(file.fileno(), permission)
        chown(file.fileno(), user, group)
        file.write(rendered)


##################################
# Custom template filters follow #
##################################
@register_filter('force_to_list')
def force_to_list(value):
    """ Convert scalars to single-item lists and leave lists untouched """
    if isinstance(value, list):
        return value
    else:
        return [value]

@register_filter('seconds_to_human')
def seconds_to_human(seconds, separator=""):
    """ Convert seconds to human-readable values like 1d6h15m23s """
    from vyos.utils.convert import seconds_to_human
    return seconds_to_human(seconds, separator=separator)

@register_filter('bytes_to_human')
def bytes_to_human(bytes, initial_exponent=0, precision=2):
    """ Convert bytes to human-readable values like 1.44M """
    from vyos.utils.convert import bytes_to_human
    return bytes_to_human(bytes, initial_exponent=initial_exponent, precision=precision)

@register_filter('human_to_bytes')
def human_to_bytes(value):
    """ Convert a data amount with a unit suffix to bytes, like 2K to 2048 """
    from vyos.utils.convert import human_to_bytes
    return human_to_bytes(value)

@register_filter('ip_from_cidr')
def ip_from_cidr(prefix):
    """ Take an IPv4/IPv6 CIDR host and strip cidr mask.
    Example:
    192.0.2.1/24 -> 192.0.2.1, 2001:db8::1/64 -> 2001:db8::1
    """
    from ipaddress import ip_interface
    return str(ip_interface(prefix).ip)

@register_filter('address_from_cidr')
def address_from_cidr(prefix):
    """ Take an IPv4/IPv6 CIDR prefix and convert the network to an "address".
    Example:
    192.0.2.0/24 -> 192.0.2.0, 2001:db8::/48 -> 2001:db8::
    """
    from ipaddress import ip_network
    return str(ip_network(prefix).network_address)

@register_filter('bracketize_ipv6')
def bracketize_ipv6(address):
    """ Place a passed IPv6 address into [] brackets, do nothing for IPv4 """
    if is_ipv6(address):
        return f'[{address}]'
    return address

@register_filter('dot_colon_to_dash')
def dot_colon_to_dash(text):
    """ Replace dot and colon to dash for string
    Example:
    192.0.2.1 => 192-0-2-1, 2001:db8::1 => 2001-db8--1
    """
    text = text.replace(":", "-")
    text = text.replace(".", "-")
    return text

@register_filter('generate_uuid4')
def generate_uuid4(text):
    """ Generate random unique ID
    Example:
      % uuid4()
      UUID('958ddf6a-ef14-4e81-8cfb-afb12456d1c5')
    """
    from uuid import uuid4
    return uuid4()

@register_filter('netmask_from_cidr')
def netmask_from_cidr(prefix):
    """ Take CIDR prefix and convert the prefix length to a "subnet mask".
    Example:
      - 192.0.2.0/24 -> 255.255.255.0
      - 2001:db8::/48 -> ffff:ffff:ffff::
    """
    from ipaddress import ip_network
    return str(ip_network(prefix).netmask)

@register_filter('netmask_from_ipv4')
def netmask_from_ipv4(address):
    """ Take IP address and search all attached interface IP addresses for the
    given one. After address has been found, return the associated netmask.

    Example:
      - 172.18.201.10 -> 255.255.255.128
    """
    from netifaces import interfaces
    from netifaces import ifaddresses
    from netifaces import AF_INET
    for interface in interfaces():
        tmp = ifaddresses(interface)
        if AF_INET in tmp:
            for af_addr in tmp[AF_INET]:
                if 'addr' in af_addr:
                    if af_addr['addr'] == address:
                        return af_addr['netmask']

    raise ValueError

@register_filter('is_ip_network')
def is_ip_network(addr):
    """ Take IP(v4/v6) address and validate if the passed argument is a network
    or a host address.

    Example:
      - 192.0.2.0          -> False
      - 192.0.2.10/24      -> False
      - 192.0.2.0/24       -> True
      - 2001:db8::         -> False
      - 2001:db8::100      -> False
      - 2001:db8::/48      -> True
      - 2001:db8:1000::/64 -> True
    """
    try:
        from ipaddress import ip_network
        # input variables must contain a / to indicate its CIDR notation
        if len(addr.split('/')) != 2:
            raise ValueError()
        ip_network(addr)
        return True
    except:
        return False

@register_filter('network_from_ipv4')
def network_from_ipv4(address):
    """ Take IP address and search all attached interface IP addresses for the
    given one. After address has been found, return the associated network
    address.

    Example:
      - 172.18.201.10 has mask 255.255.255.128 -> network is 172.18.201.0
    """
    netmask = netmask_from_ipv4(address)
    from ipaddress import ip_interface
    cidr_prefix = ip_interface(f'{address}/{netmask}').network
    return address_from_cidr(cidr_prefix)

@register_filter('is_interface')
def is_interface(interface):
    """ Check if parameter is a valid local interface name """
    from vyos.utils.network import interface_exists
    return interface_exists(interface)

@register_filter('is_ip')
def is_ip(addr):
    """ Check addr if it is an IPv4 or IPv6 address """
    return is_ipv4(addr) or is_ipv6(addr)

@register_filter('is_ipv4')
def is_ipv4(text):
    """ Filter IP address, return True on IPv4 address, False otherwise """
    from ipaddress import ip_interface
    try: return ip_interface(text).version == 4
    except: return False

@register_filter('is_ipv6')
def is_ipv6(text):
    """ Filter IP address, return True on IPv6 address, False otherwise """
    from ipaddress import ip_interface
    try: return ip_interface(text).version == 6
    except: return False

@register_filter('first_host_address')
def first_host_address(prefix):
    """ Return first usable (host) IP address from given prefix.
    Example:
      - 10.0.0.0/24 -> 10.0.0.1
      - 2001:db8::/64 -> 2001:db8::
    """
    from ipaddress import ip_interface
    tmp = ip_interface(prefix).network
    return str(tmp.network_address +1)

@register_filter('last_host_address')
def last_host_address(text):
    """ Return first usable IP address from given prefix.
    Example:
      - 10.0.0.0/24 -> 10.0.0.254
      - 2001:db8::/64 -> 2001:db8::ffff:ffff:ffff:ffff
    """
    from ipaddress import ip_interface
    from ipaddress import IPv4Network
    from ipaddress import IPv6Network

    addr = ip_interface(text)
    if addr.version == 4:
        return str(IPv4Network(addr).broadcast_address - 1)

    return str(IPv6Network(addr).broadcast_address)

@register_filter('inc_ip')
def inc_ip(address, increment):
    """ Increment given IP address by 'increment'

    Example (inc by 2):
      - 10.0.0.0/24 -> 10.0.0.2
      - 2001:db8::/64 -> 2001:db8::2
    """
    from ipaddress import ip_interface
    return str(ip_interface(address).ip + int(increment))

@register_filter('dec_ip')
def dec_ip(address, decrement):
    """ Decrement given IP address by 'decrement'

    Example (inc by 2):
      - 10.0.0.0/24 -> 10.0.0.2
      - 2001:db8::/64 -> 2001:db8::2
    """
    from ipaddress import ip_interface
    return str(ip_interface(address).ip - int(decrement))

@register_filter('compare_netmask')
def compare_netmask(netmask1, netmask2):
    """
    Compare two IP netmask if they have the exact same size.

    compare_netmask('10.0.0.0/8', '20.0.0.0/8') -> True
    compare_netmask('10.0.0.0/8', '20.0.0.0/16') -> False
    """
    from ipaddress import ip_network
    try:
        return ip_network(netmask1).netmask == ip_network(netmask2).netmask
    except:
        return False

@register_filter('isc_static_route')
def isc_static_route(subnet, router):
    # https://ercpe.de/blog/pushing-static-routes-with-isc-dhcp-server
    # Option format is:
    # <netmask>, <network-byte1>, <network-byte2>, <network-byte3>, <router-byte1>, <router-byte2>, <router-byte3>
    # where bytes with the value 0 are omitted.
    from ipaddress import ip_network
    net = ip_network(subnet)
    # add netmask
    string = str(net.prefixlen) + ','
    # add network bytes
    if net.prefixlen:
        width = net.prefixlen // 8
        if net.prefixlen % 8:
            width += 1
        string += ','.join(map(str,tuple(net.network_address.packed)[:width])) + ','

    # add router bytes
    string += ','.join(router.split('.'))

    return string

@register_filter('is_file')
def is_file(filename):
    if os.path.exists(filename):
        return os.path.isfile(filename)
    return False

@register_filter('get_dhcp_router')
def get_dhcp_router(interface):
    """ Static routes can point to a router received by a DHCP reply. This
    helper is used to get the current default router from the DHCP reply.

    Returns False of no router is found, returns the IP address as string if
    a router is found.
    """
    lease_file = directories['isc_dhclient_dir'] + f'/dhclient_{interface}.leases'
    if not os.path.exists(lease_file):
        return None

    from vyos.utils.file import read_file
    for line in read_file(lease_file).splitlines():
        if 'option routers' in line:
            (_, _, address) = line.split()
            return address.rstrip(';')

@register_filter('natural_sort')
def natural_sort(iterable):
    import re
    from jinja2.runtime import Undefined

    if isinstance(iterable, Undefined) or iterable is None:
        return list()

    def convert(text):
        return int(text) if text.isdigit() else text.lower()
    def alphanum_key(key):
        return [convert(c) for c in re.split('([0-9]+)', str(key))]

    return sorted(iterable, key=alphanum_key)

@register_filter('get_ipv4')
def get_ipv4(interface):
    """ Get interface IPv4 addresses"""
    from vyos.ifconfig import Interface
    return Interface(interface).get_addr_v4()

@register_filter('get_ipv6')
def get_ipv6(interface):
    """ Get interface IPv6 addresses"""
    from vyos.ifconfig import Interface
    return Interface(interface).get_addr_v6()

@register_filter('get_ip')
def get_ip(interface):
    """ Get interface IP addresses"""
    from vyos.ifconfig import Interface
    return Interface(interface).get_addr()

def get_first_ike_dh_group(ike_group):
    if ike_group and 'proposal' in ike_group:
        for priority, proposal in ike_group['proposal'].items():
            if 'dh_group' in proposal:
                return 'dh-group' + proposal['dh_group']
    return 'dh-group2' # Fallback on dh-group2

@register_filter('get_esp_ike_cipher')
def get_esp_ike_cipher(group_config, ike_group=None):
    pfs_lut = {
        'dh-group1'  : 'modp768',
        'dh-group2'  : 'modp1024',
        'dh-group5'  : 'modp1536',
        'dh-group14' : 'modp2048',
        'dh-group15' : 'modp3072',
        'dh-group16' : 'modp4096',
        'dh-group17' : 'modp6144',
        'dh-group18' : 'modp8192',
        'dh-group19' : 'ecp256',
        'dh-group20' : 'ecp384',
        'dh-group21' : 'ecp521',
        'dh-group22' : 'modp1024s160',
        'dh-group23' : 'modp2048s224',
        'dh-group24' : 'modp2048s256',
        'dh-group25' : 'ecp192',
        'dh-group26' : 'ecp224',
        'dh-group27' : 'ecp224bp',
        'dh-group28' : 'ecp256bp',
        'dh-group29' : 'ecp384bp',
        'dh-group30' : 'ecp512bp',
        'dh-group31' : 'curve25519',
        'dh-group32' : 'curve448'
    }

    ciphers = []
    if 'proposal' in group_config:
        for priority, proposal in group_config['proposal'].items():
            # both encryption and hash need to be specified for a proposal
            if not {'encryption', 'hash'} <= set(proposal):
                continue

            tmp = '{encryption}-{hash}'.format(**proposal)
            if 'prf' in proposal:
                tmp += '-' + proposal['prf']
            if 'dh_group' in proposal:
                tmp += '-' + pfs_lut[ 'dh-group' +  proposal['dh_group'] ]
            elif 'pfs' in group_config and group_config['pfs'] != 'disable':
                group = group_config['pfs']
                if group_config['pfs'] == 'enable':
                    group = get_first_ike_dh_group(ike_group)
                tmp += '-' + pfs_lut[group]

            ciphers.append(tmp)
    return ciphers

@register_filter('get_uuid')
def get_uuid(interface):
    """ Get interface IP addresses"""
    from uuid import uuid1
    return uuid1()

openvpn_translate = {
    'des': 'des-cbc',
    '3des': 'des-ede3-cbc',
    'bf128': 'bf-cbc',
    'bf256': 'bf-cbc',
    'aes128gcm': 'aes-128-gcm',
    'aes128': 'aes-128-cbc',
    'aes192gcm': 'aes-192-gcm',
    'aes192': 'aes-192-cbc',
    'aes256gcm': 'aes-256-gcm',
    'aes256': 'aes-256-cbc'
}

@register_filter('openvpn_cipher')
def get_openvpn_cipher(cipher):
    if cipher in openvpn_translate:
        return openvpn_translate[cipher].upper()
    return cipher.upper()

@register_filter('openvpn_ncp_ciphers')
def get_openvpn_ncp_ciphers(ciphers):
    out = []
    for cipher in ciphers:
        if cipher in openvpn_translate:
            out.append(openvpn_translate[cipher])
        else:
            out.append(cipher)
    return ':'.join(out).upper()

@register_filter('snmp_auth_oid')
def snmp_auth_oid(type):
    if type not in ['md5', 'sha', 'aes', 'des', 'none']:
        raise ValueError()

    OIDs = {
        'md5' : '.1.3.6.1.6.3.10.1.1.2',
        'sha' : '.1.3.6.1.6.3.10.1.1.3',
        'aes' : '.1.3.6.1.6.3.10.1.2.4',
        'des' : '.1.3.6.1.6.3.10.1.2.2',
        'none': '.1.3.6.1.6.3.10.1.2.1'
    }
    return OIDs[type]

@register_filter('nft_action')
def nft_action(vyos_action):
    if vyos_action == 'accept':
        return 'return'
    return vyos_action

@register_filter('nft_rule')
def nft_rule(rule_conf, fw_hook, fw_name, rule_id, ip_name='ip'):
    from vyos.firewall import parse_rule
    return parse_rule(rule_conf, fw_hook, fw_name, rule_id, ip_name)

@register_filter('nft_default_rule')
def nft_default_rule(fw_conf, fw_name, family):
    output = ['counter']
    default_action = fw_conf['default_action']
    #family = 'ipv6' if ipv6 else 'ipv4'

    if 'default_log' in fw_conf:
        action_suffix = default_action[:1].upper()
        output.append(f'log prefix "[{family}-{fw_name[:19]}-default-{action_suffix}]"')

    #output.append(nft_action(default_action))
    output.append(f'{default_action}')
    if 'default_jump_target' in fw_conf:
        target = fw_conf['default_jump_target']
        def_suffix = '6' if family == 'ipv6' else ''
        output.append(f'NAME{def_suffix}_{target}')

    output.append(f'comment "{fw_name} default-action {default_action}"')
    return " ".join(output)

@register_filter('nft_state_policy')
def nft_state_policy(conf, state):
    out = [f'ct state {state}']

    if 'log' in conf:
        log_state = state[:3].upper()
        log_action = (conf['action'] if 'action' in conf else 'accept')[:1].upper()
        out.append(f'log prefix "[STATE-POLICY-{log_state}-{log_action}]"')

        if 'log_level' in conf:
            log_level = conf['log_level']
            out.append(f'level {log_level}')

    out.append('counter')

    if 'action' in conf:
        out.append(conf['action'])

    return " ".join(out)

@register_filter('nft_intra_zone_action')
def nft_intra_zone_action(zone_conf, ipv6=False):
    if 'intra_zone_filtering' in zone_conf:
        intra_zone = zone_conf['intra_zone_filtering']
        fw_name = 'ipv6_name' if ipv6 else 'name'
        name_prefix = 'NAME6_' if ipv6 else 'NAME_'

        if 'action' in intra_zone:
            if intra_zone['action'] == 'accept':
                return 'return'
            return intra_zone['action']
        elif dict_search_args(intra_zone, 'firewall', fw_name):
            name = dict_search_args(intra_zone, 'firewall', fw_name)
            return f'jump {name_prefix}{name}'
    return 'return'

@register_filter('nft_nested_group')
def nft_nested_group(out_list, includes, groups, key):
    if not vyos_defined(out_list):
        out_list = []

    def add_includes(name):
        if key in groups[name]:
            for item in groups[name][key]:
                if item in out_list:
                    continue
                out_list.append(item)

        if 'include' in groups[name]:
            for name_inc in groups[name]['include']:
                add_includes(name_inc)

    for name in includes:
        add_includes(name)
    return out_list

@register_filter('nat_rule')
def nat_rule(rule_conf, rule_id, nat_type, ipv6=False):
    from vyos.nat import parse_nat_rule
    return parse_nat_rule(rule_conf, rule_id, nat_type, ipv6)

@register_filter('nat_static_rule')
def nat_static_rule(rule_conf, rule_id, nat_type):
    from vyos.nat import parse_nat_static_rule
    return parse_nat_static_rule(rule_conf, rule_id, nat_type)

@register_filter('conntrack_rule')
def conntrack_rule(rule_conf, rule_id, action, ipv6=False):
    ip_prefix = 'ip6' if ipv6 else 'ip'
    def_suffix = '6' if ipv6 else ''
    output = []

    if 'inbound_interface' in rule_conf:
        ifname = rule_conf['inbound_interface']
        if ifname != 'any':
            output.append(f'iifname {ifname}')

    if 'protocol' in rule_conf:
        if action != 'timeout':
            proto = rule_conf['protocol']
        else:
            for protocol, protocol_config in rule_conf['protocol'].items():
                proto = protocol
        output.append(f'meta l4proto {proto}')

    tcp_flags = dict_search_args(rule_conf, 'tcp', 'flags')
    if tcp_flags and action != 'timeout':
        from vyos.firewall import parse_tcp_flags
        output.append(parse_tcp_flags(tcp_flags))

    for side in ['source', 'destination']:
        if side in rule_conf:
            side_conf = rule_conf[side]
            prefix = side[0]

            if 'address' in side_conf:
                address = side_conf['address']
                operator = ''
                if address[0] == '!':
                    operator = '!='
                    address = address[1:]
                output.append(f'{ip_prefix} {prefix}addr {operator} {address}')

            if 'port' in side_conf:
                port = side_conf['port']
                operator = ''
                if port[0] == '!':
                    operator = '!='
                    port = port[1:]
                output.append(f'th {prefix}port {operator} {port}')

            if 'group' in side_conf:
                group = side_conf['group']

                if 'address_group' in group:
                    group_name = group['address_group']
                    operator = ''
                    if group_name[0] == '!':
                        operator = '!='
                        group_name = group_name[1:]
                    output.append(f'{ip_prefix} {prefix}addr {operator} @A{def_suffix}_{group_name}')
                # Generate firewall group domain-group
                elif 'domain_group' in group:
                    group_name = group['domain_group']
                    operator = ''
                    if group_name[0] == '!':
                        operator = '!='
                        group_name = group_name[1:]
                    output.append(f'{ip_prefix} {prefix}addr {operator} @D_{group_name}')
                elif 'network_group' in group:
                    group_name = group['network_group']
                    operator = ''
                    if group_name[0] == '!':
                        operator = '!='
                        group_name = group_name[1:]
                    output.append(f'{ip_prefix} {prefix}addr {operator} @N{def_suffix}_{group_name}')
                if 'port_group' in group:
                    group_name = group['port_group']

                    if proto == 'tcp_udp':
                        proto = 'th'

                    operator = ''
                    if group_name[0] == '!':
                        operator = '!='
                        group_name = group_name[1:]

                    output.append(f'{proto} {prefix}port {operator} @P_{group_name}')

    if action == 'ignore':
        output.append('counter notrack')
        output.append(f'comment "ignore-{rule_id}"')
    else:
        output.append(f'counter ct timeout set ct-timeout-{rule_id}')
        output.append(f'comment "timeout-{rule_id}"')

    return " ".join(output)

@register_filter('conntrack_ct_policy')
def conntrack_ct_policy(protocol_conf):
    output = []
    for item in protocol_conf:
        item_value = protocol_conf[item]
        output.append(f'{item}: {item_value}')

    return ", ".join(output)

@register_filter('range_to_regex')
def range_to_regex(num_range):
    """Convert range of numbers or list of ranges
       to regex

       % range_to_regex('11-12')
       '(1[1-2])'
       % range_to_regex(['11-12', '14-15'])
       '(1[1-2]|1[4-5])'
    """
    from vyos.range_regex import range_to_regex
    if isinstance(num_range, list):
        data = []
        for entry in num_range:
            if '-' not in entry:
                data.append(entry)
            else:
                data.append(range_to_regex(entry))
        return f'({"|".join(data)})'

    if '-' not in num_range:
        return num_range

    regex = range_to_regex(num_range)
    return f'({regex})'

@register_filter('kea_address_json')
def kea_address_json(addresses):
    from json import dumps
    from vyos.utils.network import is_addr_assigned

    out = []

    for address in addresses:
        ifname = is_addr_assigned(address, return_ifname=True, include_vrf=True)

        if not ifname:
            continue

        out.append(f'{ifname}/{address}')

    return dumps(out)

@register_filter('kea_high_availability_json')
def kea_high_availability_json(config):
    from json import dumps

    source_addr = config['source_address']
    remote_addr = config['remote']
    ha_mode = 'hot-standby' if config['mode'] == 'active-passive' else 'load-balancing'
    ha_role = config['status']

    if ha_role == 'primary':
        peer1_role = 'primary'
        peer2_role = 'standby' if ha_mode == 'hot-standby' else 'secondary'
    else:
        peer1_role = 'standby' if ha_mode == 'hot-standby' else 'secondary'
        peer2_role = 'primary'

    data = {
        'this-server-name': os.uname()[1],
        'mode': ha_mode,
        'heartbeat-delay': 10000,
        'max-response-delay': 10000,
        'max-ack-delay': 5000,
        'max-unacked-clients': 0,
        'peers': [
        {
            'name': os.uname()[1],
            'url': f'http://{source_addr}:647/',
            'role': peer1_role,
            'auto-failover': True
        },
        {
            'name': config['name'],
            'url': f'http://{remote_addr}:647/',
            'role': peer2_role,
            'auto-failover': True
        }]
    }

    if 'ca_cert_file' in config:
        data['trust-anchor'] = config['ca_cert_file']

    if 'cert_file' in config:
        data['cert-file'] = config['cert_file']

    if 'cert_key_file' in config:
        data['key-file'] = config['cert_key_file']

    return dumps(data)

@register_filter('kea_shared_network_json')
def kea_shared_network_json(shared_networks):
    from vyos.kea import kea_parse_options
    from vyos.kea import kea_parse_subnet
    from json import dumps
    out = []

    for name, config in shared_networks.items():
        if 'disable' in config:
            continue

        network = {
            'name': name,
            'authoritative': ('authoritative' in config),
            'subnet4': []
        }

        if 'option' in config:
            network['option-data'] = kea_parse_options(config['option'])

            if 'bootfile_name' in config['option']:
                network['boot-file-name'] = config['option']['bootfile_name']

            if 'bootfile_server' in config['option']:
                network['next-server'] = config['option']['bootfile_server']

        if 'subnet' in config:
            for subnet, subnet_config in config['subnet'].items():
                if 'disable' in subnet_config:
                    continue
                network['subnet4'].append(kea_parse_subnet(subnet, subnet_config))

        out.append(network)

    return dumps(out, indent=4)

@register_filter('kea6_shared_network_json')
def kea6_shared_network_json(shared_networks):
    from vyos.kea import kea6_parse_options
    from vyos.kea import kea6_parse_subnet
    from json import dumps
    out = []

    for name, config in shared_networks.items():
        if 'disable' in config:
            continue

        network = {
            'name': name,
            'subnet6': []
        }

        if 'common_options' in config:
            network['option-data'] = kea6_parse_options(config['common_options'])

        if 'interface' in config:
            network['interface'] = config['interface']

        if 'subnet' in config:
            for subnet, subnet_config in config['subnet'].items():
                network['subnet6'].append(kea6_parse_subnet(subnet, subnet_config))

        out.append(network)

    return dumps(out, indent=4)

@register_test('vyos_defined')
def vyos_defined(value, test_value=None, var_type=None):
    """
    Jinja2 plugin to test if a variable is defined and not none - vyos_defined
    will test value if defined and is not none and return true or false.

    If test_value is supplied, the value must also pass == test_value to return true.
    If var_type is supplied, the value must also be of the specified class/type

    Examples:
    1. Test if var is defined and not none:
    {% if foo is vyos_defined %}
    ...
    {% endif %}

    2. Test if variable is defined, not none and has value "something"
    {% if bar is vyos_defined("something") %}
    ...
    {% endif %}

    Parameters
    ----------
    value : any
        Value to test from ansible
    test_value : any, optional
        Value to test in addition of defined and not none, by default None
    var_type : ['float', 'int', 'str', 'list', 'dict', 'tuple', 'bool'], optional
        Type or Class to test for

    Returns
    -------
    boolean
        True if variable matches criteria, False in other cases.

    Implementation inspired and re-used from https://github.com/aristanetworks/ansible-avd/
    """

    from jinja2 import Undefined

    if isinstance(value, Undefined) or value is None:
        # Invalid value - return false
        return False
    elif test_value is not None and value != test_value:
        # Valid value but not matching the optional argument
        return False
    elif str(var_type).lower() in ['float', 'int', 'str', 'list', 'dict', 'tuple', 'bool'] and str(var_type).lower() != type(value).__name__:
        # Invalid class - return false
        return False
    else:
        # Valid value and is matching optional argument if provided - return true
        return True
