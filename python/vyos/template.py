# Copyright 2019-2020 VyOS maintainers and contributors <maintainers@vyos.io>
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

from vyos.defaults import directories
from vyos.util import chmod
from vyos.util import chown
from vyos.util import makedir

# Holds template filters registered via register_filter()
_FILTERS = {}

# reuse Environments with identical settings to improve performance
@functools.lru_cache(maxsize=2)
def _get_environment(location=None):
    if location is None:
        loc_loader=FileSystemLoader(directories["templates"])
    else:
        loc_loader=FileSystemLoader(location)
    env = Environment(
        # Don't check if template files were modified upon re-rendering
        auto_reload=False,
        # Cache up to this number of templates for quick re-rendering
        cache_size=100,
        loader=loc_loader,
        trim_blocks=True,
    )
    env.filters.update(_FILTERS)
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
def first_host_address(text):
    """ Return first usable (host) IP address from given prefix.
    Example:
      - 10.0.0.0/24 -> 10.0.0.1
      - 2001:db8::/64 -> 2001:db8::
    """
    from ipaddress import ip_interface
    from ipaddress import IPv4Network
    from ipaddress import IPv6Network

    addr = ip_interface(text)
    if addr.version == 4:
        return str(addr.ip +1)
    return str(addr.ip)

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

@register_filter('get_ipv4')
def get_ipv4(interface):
    """ Get interface IPv4 addresses"""
    from vyos.ifconfig import Interface
    return Interface(interface).get_addr_v4()

@register_filter('nft_action')
def nft_action(vyos_action):
    if vyos_action == 'accept':
        return 'return'
    return vyos_action

@register_filter('nft_rule')
def nft_rule(rule_conf, fw_name, rule_id, ip_name='ip'):
    from vyos.firewall import parse_rule
    return parse_rule(rule_conf, fw_name, rule_id, ip_name)

@register_filter('nft_default_rule')
def nft_default_rule(fw_conf, fw_name):
    output = ['counter']
    default_action = fw_conf.get('default_action', 'accept')

    if 'enable_default_log' in fw_conf:
        action_suffix = default_action[:1].upper()
        output.append(f'log prefix "[{fw_name[:19]}-default-{action_suffix}] "')

    output.append(nft_action(default_action))
    output.append(f'comment "{fw_name} default-action {default_action}"')
    return " ".join(output)
