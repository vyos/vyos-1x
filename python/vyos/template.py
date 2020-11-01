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
from vyos.util import chmod, chown, makedir


# Holds template filters registered via register_filter()
_FILTERS = {}


# reuse Environments with identical trim_blocks setting to improve performance
@functools.lru_cache(maxsize=2)
def _get_environment(trim_blocks):
    env = Environment(
        # Don't check if template files were modified upon re-rendering
        auto_reload=False,
        # Cache up to this number of templates for quick re-rendering
        cache_size=100,
        loader=FileSystemLoader(directories["templates"]),
        trim_blocks=trim_blocks,
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


def render_to_string(template, content, trim_blocks=False, formater=None):
    """Render a template from the template directory, raise on any errors.

    :param template: the path to the template relative to the template folder
    :param content: the dictionary of variables to put into rendering context
    :param trim_blocks: controls the trim_blocks jinja2 feature
    :param formater:
        if given, it has to be a callable the rendered string is passed through

    The parsed template files are cached, so rendering the same file multiple times
    does not cause as too much overhead.
    If used everywhere, it could be changed to load the template from Python
    environment variables from an importable Python module generated when the Debian
    package is build (recovering the load time and overhead caused by having the
    file out of the code).
    """
    template = _get_environment(bool(trim_blocks)).get_template(template)
    rendered = template.render(content)
    if formater is not None:
        rendered = formater(rendered)
    return rendered


def render(
    destination,
    template,
    content,
    trim_blocks=False,
    formater=None,
    permission=None,
    user=None,
    group=None,
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
    rendered = render_to_string(template, content, trim_blocks, formater)

    # Write to file
    with open(destination, "w") as file:
        chmod(file.fileno(), permission)
        chown(file.fileno(), user, group)
        file.write(rendered)


##################################
# Custom template filters follow #
##################################

@register_filter('address_from_cidr')
def vyos_address_from_cidr(text):
    """ Take an IPv4/IPv6 CIDR prefix and convert the network to an "address".
    Example:
    192.0.2.0/24 -> 192.0.2.0, 2001:db8::/48 -> 2001:db8::
    """
    from ipaddress import ip_network
    return str(ip_network(text).network_address)

@register_filter('netmask_from_cidr')
def vyos_netmask_from_cidr(text):
    """ Take CIDR prefix and convert the prefix length to a "subnet mask".
    Example:
      - 192.0.2.0/24 -> 255.255.255.0
      - 2001:db8::/48 -> ffff:ffff:ffff::
    """
    from ipaddress import ip_network
    return str(ip_network(text).netmask)

@register_filter('ipv4')
def vyos_ipv4(text):
    """ Filter IP address, return True on IPv4 address, False otherwise """
    from ipaddress import ip_interface
    return ip_interface(text).version == 4

@register_filter('ipv6')
def vyos_ipv6(text):
    """ Filter IP address, return True on IPv6 address, False otherwise """
    from ipaddress import ip_interface
    return ip_interface(text).version == 6

@register_filter('first_host_address')
def vyos_first_host_address(text):
    """ Return first usable (host) IP address from given prefix.
    Example:
      - 10.0.0.0/24 -> 10.0.0.1
      - 2001:db8::/64 -> 2001:db8::1
    """
    from ipaddress import ip_interface
    from ipaddress import IPv4Network
    from ipaddress import IPv6Network

    addr = ip_interface(text)
    if addr.version == 4:
        return str(addr.ip +1)
    return str(addr.ip)

@register_filter('last_host_address')
def vyos_last_host_address(text):
    """ Return first usable IP address from given prefix.
    Example:
      - 10.0.0.0/24 -> 10.0.0.1
      - 2001:db8::/64 -> 2001:db8::1
    """
    from ipaddress import ip_interface
    from ipaddress import IPv4Network
    from ipaddress import IPv6Network

    addr = ip_interface(text)
    if addr.version == 4:
        addr = IPv4Network(addr)
    else:
        addr = IPv6Network(addr)

    return str(addr.broadcast_address -1)

@register_filter('inc_ip')
def vyos_inc_ip(text, increment):
    """ Return first usable IP address from given prefix.
    Example:
      - 10.0.0.0/24 -> 10.0.0.1
      - 2001:db8::/64 -> 2001:db8::1
    """
    from ipaddress import ip_interface
    return str(ip_interface(text).ip + int(increment))
