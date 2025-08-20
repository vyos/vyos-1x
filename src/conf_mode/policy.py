#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
from sys import exit

from vyos.config import Config
from vyos.configverify import has_frr_protocol_in_dict
from vyos.frrender import FRRender
from vyos.frrender import frr_protocols
from vyos.frrender import get_frrender_dict
from vyos.utils.dict import dict_search
from vyos.utils.process import is_systemd_service_running
from vyos import ConfigError
from vyos.base import Warning
from vyos import airbag
airbag.enable()

# Sanity checks for large-community-list regex:
# * Require complete 3-tuples, no blank members. Catch missed & doubled colons. 
# * Permit appropriate community separators (whitespace, underscore)
# * Permit common regex between tuples while requiring at least one separator
#   (eg, "1:1:1_.*_4:4:4", matching "1:1:1 4:4:4" and "1:1:1 2:2:2 4:4:4",
#        but not "1:1:13 24:4:4")
# Best practice: stick with basic patterns, mind your wildcards and whitespace.
# Regex that doesn't match this pattern will be allowed with a warning. 
large_community_regex_pattern = r'([^: _]+):([^: _]+):([^: _]+)([ _]([^:]+):([^: _]+):([^: _]+))*'

def community_action_compatibility(actions: dict) -> bool:
    """
    Check compatibility of values in community and large community sections
    :param actions: dictionary with community
    :type actions: dict
    :return: true if compatible, false if not
    :rtype: bool
    """
    if ('none' in actions) and ('replace' in actions or 'add' in actions):
        return False
    if 'replace' in actions and 'add' in actions:
        return False
    if ('delete' in actions) and ('none' in actions or 'replace' in actions):
        return False
    return True


def extcommunity_action_compatibility(actions: dict) -> bool:
    """
    Check compatibility of values in extended community sections
    :param actions: dictionary with community
    :type actions: dict
    :return: true if compatible, false if not
    :rtype: bool
    """
    if ('none' in actions) and (
            'rt' in actions or 'soo' in actions or 'bandwidth' in actions or 'bandwidth_non_transitive' in actions):
        return False
    if ('bandwidth_non_transitive' in actions) and ('bandwidth' not in actions):
        return False
    return True

def routing_policy_find(key, dictionary):
    # Recursively traverse a dictionary and extract the value assigned to
    # a given key as generator object. This is made for routing policies,
    # thus also import/export is checked
    for k, v in dictionary.items():
        if k == key:
            if isinstance(v, dict):
                for a, b in v.items():
                    if a in ['import', 'export']:
                        yield b
            else:
                yield v
        elif isinstance(v, dict):
            for result in routing_policy_find(key, v):
                yield result
        elif isinstance(v, list):
            for d in v:
                if isinstance(d, dict):
                    for result in routing_policy_find(key, d):
                        yield result


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    return get_frrender_dict(conf)


def verify(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'policy'):
        return None

    policy_types = ['access_list', 'access_list6', 'as_path_list',
                    'community_list', 'extcommunity_list',
                    'large_community_list', 'prefix_list',
                    'prefix_list6', 'route_map']

    policy = config_dict['policy']
    for protocol in frr_protocols:
        if protocol not in config_dict:
            continue
        if 'protocol' not in policy:
            policy.update({'protocol': {}})
        policy['protocol'].update({protocol : config_dict[protocol]})

    for policy_type in policy_types:
        # Bail out early and continue with next policy type
        if policy_type not in policy:
            continue

        # instance can be an ACL name/number, prefix-list name or route-map name
        for instance, instance_config in policy[policy_type].items():
            # If no rule was found within the instance ... sad, but we can leave
            # early as nothing needs to be verified
            if 'rule' not in instance_config:
                continue

            # human readable instance name (hypen instead of underscore)
            policy_hr = policy_type.replace('_', '-')
            entries = []
            for rule, rule_config in instance_config['rule'].items():
                mandatory_error = f'must be specified for "{policy_hr} {instance} rule {rule}"!'
                if 'action' not in rule_config:
                    raise ConfigError(f'Action {mandatory_error}')

                if policy_type == 'access_list':
                    if 'source' not in rule_config:
                        raise ConfigError(f'A source {mandatory_error}')

                    if int(instance) in range(100, 200) or int(
                            instance) in range(2000, 2700):
                        if 'destination' not in rule_config:
                            raise ConfigError(
                                f'A destination {mandatory_error}')

                if policy_type == 'access_list6':
                    if 'source' not in rule_config:
                        raise ConfigError(f'A source {mandatory_error}')

                if policy_type in ['as_path_list', 'community_list',
                                   'extcommunity_list',
                                   'large_community_list']:
                    if 'regex' not in rule_config:
                        raise ConfigError(f'A regex {mandatory_error}')

                if policy_type == 'large_community_list':
                    if not re.fullmatch(large_community_regex_pattern, rule_config['regex']):
                        Warning(f'"policy large-community-list {instance} rule {rule} regex" does not follow expected form and may not match as expected.')

                if policy_type in ['prefix_list', 'prefix_list6']:
                    if 'prefix' not in rule_config:
                        raise ConfigError(f'A prefix {mandatory_error}')

                    if rule_config in entries:
                        raise ConfigError(
                            f'Rule "{rule}" contains a duplicate prefix definition!')
                    entries.append(rule_config)

    # route-maps tend to be a bit more complex so they get their own verify() section
    if 'route_map' in policy:
        for route_map, route_map_config in policy['route_map'].items():
            if 'rule' not in route_map_config:
                continue

            for rule, rule_config in route_map_config['rule'].items():
                # Action 'deny' cannot be used with "continue" or "on-match"
                # FRR does not validate it T4827, T6676
                if rule_config['action'] == 'deny' and ('continue' in rule_config or 'on_match' in rule_config):
                    raise ConfigError(f'rule {rule} "continue" or "on-match" cannot be used with action deny!')

                # Specified community-list must exist
                tmp = dict_search('match.community.community_list',
                                  rule_config)
                if tmp and tmp not in policy.get('community_list', []):
                    raise ConfigError(f'community-list {tmp} does not exist!')

                # Specified extended community-list must exist
                tmp = dict_search('match.extcommunity', rule_config)
                if tmp and tmp not in policy.get('extcommunity_list', []):
                    raise ConfigError(
                        f'extcommunity-list {tmp} does not exist!')

                # Specified large-community-list must exist
                tmp = dict_search('match.large_community.large_community_list',
                                  rule_config)
                if tmp and tmp not in policy.get('large_community_list', []):
                    raise ConfigError(
                        f'large-community-list {tmp} does not exist!')

                # Specified prefix-list must exist
                tmp = dict_search('match.ip.address.prefix_list', rule_config)
                if tmp and tmp not in policy.get('prefix_list', []):
                    raise ConfigError(f'prefix-list {tmp} does not exist!')

                # Specified prefix-list must exist
                tmp = dict_search('match.ipv6.address.prefix_list',
                                  rule_config)
                if tmp and tmp not in policy.get('prefix_list6', []):
                    raise ConfigError(f'prefix-list6 {tmp} does not exist!')

                # Specified access_list6 in nexthop must exist
                tmp = dict_search('match.ipv6.nexthop.access_list',
                                  rule_config)
                if tmp and tmp not in policy.get('access_list6', []):
                    raise ConfigError(f'access_list6 {tmp} does not exist!')

                # Specified prefix-list6 in nexthop must exist
                tmp = dict_search('match.ipv6.nexthop.prefix_list',
                                  rule_config)
                if tmp and tmp not in policy.get('prefix_list6', []):
                    raise ConfigError(f'prefix-list6 {tmp} does not exist!')

                tmp = dict_search('set.community.delete', rule_config)
                if tmp and tmp not in policy.get('community_list', []):
                    raise ConfigError(f'community-list {tmp} does not exist!')

                tmp = dict_search('set.large_community.delete',
                                  rule_config)
                if tmp and tmp not in policy.get('large_community_list', []):
                    raise ConfigError(
                        f'large-community-list {tmp} does not exist!')

                if 'set' in rule_config:
                    rule_action = rule_config['set']
                    if 'community' in rule_action:
                        if not community_action_compatibility(
                                rule_action['community']):
                            raise ConfigError(
                                f'Unexpected combination between action replace, add, delete or none in community')
                    if 'large_community' in rule_action:
                        if not community_action_compatibility(
                                rule_action['large_community']):
                            raise ConfigError(
                                f'Unexpected combination between action replace, add, delete or none in large-community')
                    if 'extcommunity' in rule_action:
                        if not extcommunity_action_compatibility(
                                rule_action['extcommunity']):
                            raise ConfigError(
                                f'Unexpected combination between none, rt, soo, bandwidth, bandwidth-non-transitive in extended-community')
    # When routing protocols are active some use prefix-lists, route-maps etc.
    # to apply the systems routing policy to the learned or redistributed routes.
    # When the "routing policy" changes and policies, route-maps etc. are deleted,
    # it is our responsibility to verify that the policy can not be deleted if it
    # is used by any routing protocol
    # Check if any routing protocol is activated
    if 'protocol' in policy:
        for policy_type in policy_types:
            for policy_name in list(set(routing_policy_find(policy_type, policy['protocol']))):
                found = False
                if policy_type in policy and policy_name in policy[policy_type]:
                    found = True
                # BGP uses prefix-list for selecting both an IPv4 or IPv6 AFI related
                # list - we need to go the extra mile here and check both prefix-lists
                if policy_type == 'prefix_list' and 'prefix_list6' in policy and policy_name in \
                        policy['prefix_list6']:
                    found = True
                if not found:
                    tmp = policy_type.replace('_', '-')
                    raise ConfigError(
                        f'Can not delete {tmp} "{policy_name}", still in use!')

    return None


def generate(config_dict):
    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().generate(config_dict)
    return None

def apply(config_dict):
    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().apply()
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
