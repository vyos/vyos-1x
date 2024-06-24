#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import argparse
from vyos.configquery import ConfigTreeQuery


def convert_to_set_commands(config_dict, parent_key=''):
    """
    Converts a configuration dictionary into a list of set commands.

    Args:
        config_dict (dict): The configuration dictionary.
        parent_key (str): The parent key for nested dictionaries.

    Returns:
        list: A list of set commands.
    """
    commands = []
    for key, value in config_dict.items():
        current_key = parent_key + key if parent_key else key

        if isinstance(value, dict):
            if not value:
                commands.append(f"set {current_key}")
            else:
                commands.extend(
                    convert_to_set_commands(value, f"{current_key} "))

        elif isinstance(value, list):
            for item in value:
                commands.append(f"set {current_key} '{item}'")

        elif isinstance(value, str):
            commands.append(f"set {current_key} '{value}'")

    return commands


def change_rule_numbers(config_dict, start, step):
    """
    Changes rule numbers in the configuration dictionary.

    Args:
        config_dict (dict): The configuration dictionary.
        start (int): The starting rule number.
        step (int): The step to increment the rule numbers.

    Returns:
        None
    """
    if 'rule' in config_dict:
        rule_dict = config_dict['rule']
        updated_rule_dict = {}
        rule_num = start
        for rule_key in sorted(rule_dict.keys()):
            updated_rule_dict[str(rule_num)] = rule_dict[rule_key]
            rule_num += step
        config_dict['rule'] = updated_rule_dict

    for key in config_dict:
        if isinstance(config_dict[key], dict):
            change_rule_numbers(config_dict[key], start, step)


def convert_rule_keys_to_int(config_dict, prev_key=None):
    """
    Converts rule keys in the configuration dictionary to integers.

    Args:
        config_dict (dict or list): The configuration dictionary or list.

    Returns:
        dict or list: The modified dictionary or list.
    """
    if isinstance(config_dict, dict):
        new_dict = {}
        for key, value in config_dict.items():
            # Convert key to integer if possible
            new_key = int(key) if key.isdigit() and prev_key == 'rule' else key

            # Recur for nested dictionaries
            if isinstance(value, dict):
                new_value = convert_rule_keys_to_int(value, key)
            else:
                new_value = value

            new_dict[new_key] = new_value

        return new_dict
    elif isinstance(config_dict, list):
        return [convert_rule_keys_to_int(item) for item in config_dict]
    else:
        return config_dict


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Convert dictionary to set commands with rule number modifications.')
    parser.add_argument('--service', type=str, help='Name of service')
    parser.add_argument('--start', type=int, default=100, help='Start rule number (default: 100)')
    parser.add_argument('--step', type=int, default=10, help='Step for rule numbers (default: 10)')
    args = parser.parse_args()

    config = ConfigTreeQuery()
    if not config.exists(args.service):
        print(f'{args.service} is not configured')
        exit(1)

    config_dict = config.get_config_dict(args.service)

    if 'firewall' in config_dict:
        # Remove global-options, group and flowtable as they don't need sequencing
        for item in ['global-options', 'group', 'flowtable']:
            if item in config_dict['firewall']:
                del config_dict['firewall'][item]

    # Convert rule keys to integers, rule "10" -> rule 10
    # This is necessary for sorting the rules
    config_dict = convert_rule_keys_to_int(config_dict)

    # Apply rule number modifications
    change_rule_numbers(config_dict, start=args.start, step=args.step)

    # Convert to 'set' commands
    set_commands = convert_to_set_commands(config_dict)

    print()
    for command in set_commands:
        print(command)
    print()
