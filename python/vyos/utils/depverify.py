# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

from vyos.utils.dict import dict_search
from vyos.utils.dict import dict_search_recursive
from vyos.utils.dict import dict_search_recursive_values
from vyos.utils.dict import dict_set_nested


def is_subsequence(check, path):
    """
    Return True if all items in 'check' appear in order within 'path'.

    Items do not need to be contiguous; only their relative order must match.
    This implementation performs a single forward pass over 'path'.

    Parameters:
        check: Sequence of items to find, in the given order.
        path: Iterable to search for the ordered items.

    Returns:
        bool: True if 'check' is an ordered subsequence of 'path', otherwise False.
    """
    it = iter(path)
    return all(item in it for item in check)


def check_warning_or_error(
    match: list[str],
    dep: dict,
    phrases: list[str] = [],
    ignore: str = '',
    is_warning: bool = False,
):
    """
    Classify a dependency match as a warning or an error and record it.

    If 'is_warning' is True, the match is appended to
    dep['dependencies']['warnings'] and no further checks are performed.
    Otherwise, if any phrase in 'phrases' appears as an ordered subsequence
    within 'match' (space-splitting each phrase), the match is recorded as a
    warning. If no phrase matches, the match is recorded as an error unless
    'ignore' is set and appears as an ordered subsequence within 'match'.

    Parameters:
        match: List of tokens describing the configuration path for the hit.
        dep: Accumulator dict with 'dependencies.warnings' and
             'dependencies.errors' lists to be mutated in-place.
        phrases: List of phrases that downgrade a hit to a warning when their
                 tokens appear in order within 'match'.
        ignore: Optional phrase; if its tokens appear in order within 'match',
                suppresses adding the hit to errors.
        is_warning: Force classification as a warning (bypasses phrase/ignore checks).

    Returns:
        updates 'dep' in-place.
    """
    if is_warning:
        dep['dependencies']['warnings'].append(match)
        return

    for phrase in phrases:
        if is_subsequence(phrase.split(), match):
            dep['dependencies']['warnings'].append(match)
            break
    else:
        if not ignore or not is_subsequence(ignore.split(), match):
            dep['dependencies']['errors'].append(match)


def verify_interface_dependencies(conf: dict, interface: str, ignore: str = ''):
    """
    Analyze configuration to find and classify references to an interface.

    The function scans relevant top-level sections (container, firewall,
    interfaces, nat, nat66, policy, protocols, qos, service, system) for any
    occurrences of 'interface'. Each hit is routed through
    check_warning_or_error to determine whether it should be recorded as a
    warning or an error. The optional 'ignore' phrase can suppress specific
    error entries when its tokens appear in order within a matched path.

    Parameters:
        conf: Configuration dictionary to search.
        interface: Interface name to look for (for example, "br0").
        ignore: Optional phrase whose ordered tokens suppress adding a hit to errors.

    Returns:
        dict: Summary with optional keys:
              - 'warnings' (bool) and 'warnings_msg' (str)
              - 'errors'   (bool) and 'errors_msg'   (str)
    """
    container = dict_search('container', conf)
    firewall = dict_search('firewall', conf)
    interfaces = dict_search('interfaces', conf)
    nat = dict_search('nat', conf)
    nat66 = dict_search('nat66', conf)
    policy = dict_search('policy', conf)
    protocols = dict_search('protocols', conf)
    qos = dict_search('qos', conf)
    service = dict_search('service', conf)
    system = dict_search('system', conf)

    dep = {}

    dict_set_nested(f'dependencies.warnings', [], dep)
    dict_set_nested(f'dependencies.errors', [], dep)

    ########## Container ##########
    for container_match in dict_search_recursive_values(container, interface):
        check_warning_or_error(['container', *container_match], dep, is_warning=True)
    for found_name, found_path in dict_search_recursive(container, interface):
        check_warning_or_error(['container', *found_path], dep)

    ########## Firewall ##########
    for fw_match in dict_search_recursive_values(firewall, interface):
        check_warning_or_error(['firewall', *fw_match], dep, is_warning=True)
    for found_name, found_path in dict_search_recursive(firewall, interface):
        check_warning_or_error(['firewall', *found_path], dep)

    ########## Interfaces ##########
    for int_match in dict_search_recursive_values(interfaces, interface):
        check_warning_or_error(
            ['interfaces', *int_match], dep, ignore=ignore, is_warning=True
        )
    for found_name, found_path in dict_search_recursive(interfaces, interface):
        check_warning_or_error(['interfaces', *found_path], dep, ignore=ignore)

    ########## Nat ##########
    nat_warning_list = ["nat source", "nat destination"]
    for nat_match in dict_search_recursive_values(nat, interface):
        check_warning_or_error(['nat', *nat_match], dep, is_warning=True)
    for found_name, found_path in dict_search_recursive(nat, interface):
        check_warning_or_error(['nat', *found_path], dep, nat_warning_list)

    ########## Nat66 ##########
    nat66_warning_list = ["nat66 source", "nat66 destination"]
    for nat66_match in dict_search_recursive_values(nat66, interface):
        check_warning_or_error(['nat66', *nat66_match], dep, is_warning=True)
    for found_name, found_path in dict_search_recursive(nat66, interface):
        check_warning_or_error(['nat66', *found_path], dep, nat66_warning_list)

    ########## Policy ##########
    policy_warning_list = ["policy route interface"]
    for policy_match in dict_search_recursive_values(policy, interface):
        check_warning_or_error(['policy', *policy_match], dep, is_warning=True)
    for found_name, found_path in dict_search_recursive(policy, interface):
        check_warning_or_error(['policy', *found_path], dep, policy_warning_list)

    ########## Protocols ##########
    proto_warning_list = [
        "protocols static",
        "protocols babel",
        "protocols bfd",
        "protocols bgp",
        "protocols failover",
        "protocols rip",
    ]
    for proto_match in dict_search_recursive_values(protocols, interface):
        check_warning_or_error(['protocols', *proto_match], dep, is_warning=True)
    for found_name, found_path in dict_search_recursive(protocols, interface):
        check_warning_or_error(['protocols', *found_path], dep, proto_warning_list)

    ########## QoS ##########
    qos_warning_list = ["qos source", "qos destination"]
    for qos_match in dict_search_recursive_values(qos, interface):
        check_warning_or_error(['qos', *qos_match], dep, is_warning=True)
    for found_name, found_path in dict_search_recursive(qos, interface):
        check_warning_or_error(['qos', *found_path], dep, qos_warning_list)

    ########## Services ##########
    service_warning_list = [
        "service dns dynamic",
        "service pppoe_server",
        "service lldp",
        "service suricata",
    ]
    for service_match in dict_search_recursive_values(service, interface):
        check_warning_or_error(['service', *service_match], dep, is_warning=True)
    for found_name, found_path in dict_search_recursive(service, interface):
        check_warning_or_error(['service', *found_path], dep, service_warning_list)

    ########## System ##########
    system_warning_list = [
        "system flow_accounting",
        "system name-server",
        "system sflow",
    ]
    for system_match in dict_search_recursive_values(system, interface):
        check_warning_or_error(['system', *system_match], dep, is_warning=True)
    for found_name, found_path in dict_search_recursive(system, interface):
        check_warning_or_error(['system', *found_path], dep, system_warning_list)

    out = {}
    dependency_warnings = dict_search('dependencies.warnings', dep)
    dependency_errors = dict_search('dependencies.errors', dep)

    if dependency_warnings:
        warning_paths = "\n".join("- " + " ".join(dep) for dep in dependency_warnings)
        msg = f"{interface} is configured in the following configuration paths:\n{warning_paths}"
        out['warnings'] = True
        out['warnings_msg'] = msg
    if dependency_errors:
        error_paths = "\n".join("- " + " ".join(dep) for dep in dependency_errors)
        msg = (
            f"{interface} can't be deleted while configured in the following configuration paths:"
            "\n"
            f"{error_paths}"
        )
        out['errors'] = True
        out['errors_msg'] = msg
    return out
