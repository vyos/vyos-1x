#!/usr/bin/env python3
#
# Copyright (C) 2021-2022 VyOS maintainers and contributors
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

from sys import exit

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.template import render_to_string
from vyos.utils.dict import dict_search
from vyos import ConfigError
from vyos import frr
from vyos import airbag

airbag.enable()


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

    base = ['policy']
    policy = conf.get_config_dict(base, key_mangling=('-', '_'),
                                  get_first_key=True,
                                  no_tag_node_value_mangle=True)

    # We also need some additional information from the config, prefix-lists
    # and route-maps for instance. They will be used in verify().
    #
    # XXX: one MUST always call this without the key_mangling() option! See
    # vyos.configverify.verify_common_route_maps() for more information.
    tmp = conf.get_config_dict(['protocols'], key_mangling=('-', '_'),
                               no_tag_node_value_mangle=True)
    # Merge policy dict into "regular" config dict
    policy = dict_merge(tmp, policy)
    return policy


def verify(policy):
    if not policy:
        return None

    for policy_type in ['access_list', 'access_list6', 'as_path_list',
                        'community_list', 'extcommunity_list',
                        'large_community_list',
                        'prefix_list', 'prefix_list6', 'route_map']:
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
    if 'protocols' in policy:
        for policy_type in ['access_list', 'access_list6', 'as_path_list',
                            'community_list',
                            'extcommunity_list', 'large_community_list',
                            'prefix_list', 'route_map']:
            if policy_type in policy:
                for policy_name in list(set(routing_policy_find(policy_type,
                                                                policy[
                                                                    'protocols']))):
                    found = False
                    if policy_name in policy[policy_type]:
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


def generate(policy):
    if not policy:
        return None
    policy['new_frr_config'] = render_to_string('frr/policy.frr.j2', policy)
    return None


def apply(policy):
    bgp_daemon = 'bgpd'
    zebra_daemon = 'zebra'

    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()

    # The route-map used for the FIB (zebra) is part of the zebra daemon
    frr_cfg.load_configuration(bgp_daemon)
    frr_cfg.modify_section(r'^bgp as-path access-list .*')
    frr_cfg.modify_section(r'^bgp community-list .*')
    frr_cfg.modify_section(r'^bgp extcommunity-list .*')
    frr_cfg.modify_section(r'^bgp large-community-list .*')
    frr_cfg.modify_section(r'^route-map .*', stop_pattern='^exit',
                           remove_stop_mark=True)
    if 'new_frr_config' in policy:
        frr_cfg.add_before(frr.default_add_before, policy['new_frr_config'])
    frr_cfg.commit_configuration(bgp_daemon)

    # The route-map used for the FIB (zebra) is part of the zebra daemon
    frr_cfg.load_configuration(zebra_daemon)
    frr_cfg.modify_section(r'^access-list .*')
    frr_cfg.modify_section(r'^ipv6 access-list .*')
    frr_cfg.modify_section(r'^ip prefix-list .*')
    frr_cfg.modify_section(r'^ipv6 prefix-list .*')
    frr_cfg.modify_section(r'^route-map .*', stop_pattern='^exit',
                           remove_stop_mark=True)
    if 'new_frr_config' in policy:
        frr_cfg.add_before(frr.default_add_before, policy['new_frr_config'])
    frr_cfg.commit_configuration(zebra_daemon)

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
