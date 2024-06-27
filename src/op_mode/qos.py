#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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
# This script parses output from the 'tc' command and provides table or list output
import sys
import typing
import json
from tabulate import tabulate

import vyos.opmode
from vyos.configquery import op_mode_config_dict
from vyos.utils.process import cmd
from vyos.utils.network import interface_exists

def detailed_output(dataset, headers):
    for data in dataset:
        adjusted_rule = data + [""] * (len(headers) - len(data)) # account for different header length, like default-action
        transformed_rule = [[header, adjusted_rule[i]] for i, header in enumerate(headers) if i < len(adjusted_rule)] # create key-pair list from headers and rules lists; wrap at 100 char

        print(tabulate(transformed_rule, tablefmt="presto"))
        print()

def get_tc_info(interface_dict, interface_name, policy_type):
    policy_name = interface_dict.get(interface_name, {}).get('egress')
    if not policy_name:
        return None, None
    
    class_dict = op_mode_config_dict(['qos', 'policy', policy_type, policy_name], key_mangling=('-', '_'),
                            get_first_key=True)
    if not class_dict:
        return None, None

    return policy_name, class_dict

def format_data_type(num, suffix):
    if num < 10**3:
        return f"{num}  {suffix}"
    elif num < 10**6:
        return f"{num / 10**3:.3f} K{suffix}"
    elif num < 10**9:
        return f"{num / 10**6:.3f} M{suffix}"
    elif num < 10**12:
        return f"{num / 10**9:.3f} G{suffix}"
    elif num < 10**15:
        return f"{num / 10**12:.3f} T{suffix}"
    elif num < 10**18:
        return f"{num / 10**15:.3f} P{suffix}"
    else:
        return f"{num / 10**18:.3f} E{suffix}"

def show_shaper(raw: bool, ifname: typing.Optional[str], classn: typing.Optional[str], detail: bool):
    # Scope which interfaces will output data
    if ifname:
        if not interface_exists(ifname):
            raise vyos.opmode.Error(f"{ifname} does not exist!")
        
        interface_dict = {ifname: op_mode_config_dict(['qos', 'interface', ifname], key_mangling=('-', '_'),
                            get_first_key=True)}   
        if not interface_dict[ifname]:
            raise vyos.opmode.Error(f"QoS is not applied to {ifname}!")
        
    else:
        interface_dict = op_mode_config_dict(['qos', 'interface'], key_mangling=('-', '_'),
                            get_first_key=True)     
        if not interface_dict:
            raise vyos.opmode.Error(f"QoS is not applied to any interface!")
    

    raw_dict = {'qos': {}}
    for i in interface_dict.keys():
        interface_name = i
        output_list = []
        output_dict = {'classes': {}}
        raw_dict['qos'][interface_name] = {}
        
        # Get configuration node data
        policy_name, class_dict = get_tc_info(interface_dict, interface_name, 'shaper')
        if not policy_name:
            continue        

        class_data = json.loads(cmd(f"tc -j -s class show dev {i}"))
        qdisc_data = json.loads(cmd(f"tc -j qdisc show dev {i}"))

        if class_dict:
            # Gather qdisc information (e.g. Queue Type)
            qdisc_dict = {}
            for qdisc in qdisc_data:
                if qdisc.get('root'):
                    qdisc_dict['root'] = qdisc
                    continue

                class_id = int(qdisc.get('parent').split(':')[1], 16)

                if class_dict.get('class', {}).get(str(class_id)):
                    qdisc_dict[str(class_id)] = qdisc
                else:
                    qdisc_dict['default'] = qdisc

            # Gather class information
            for classes in class_data:
                if classes.get('rate'):
                    class_id = int(classes.get('handle').split(':')[1], 16)

                    # Get name of class
                    if classes.get('root'):
                        class_name = 'root'
                        output_dict['classes'][class_name] = {}
                    elif class_dict.get('class', {}).get(str(class_id)):
                        class_name = str(class_id)
                        output_dict['classes'][class_name] = {}
                    else:
                        class_name = 'default'
                        output_dict['classes'][class_name] = {}

                    if classn:
                        if classn != class_name and class_name != 'default' and class_name != 'root':
                            output_dict['classes'].pop(class_name, None)
                            continue

                    tmp = output_dict['classes'][class_name]

                    tmp['interface_name'] = interface_name
                    tmp['policy_name'] = policy_name
                    tmp['direction'] = 'egress'
                    tmp['class_name'] = class_name
                    tmp['queue_type'] = qdisc_dict.get(class_name, {}).get('kind')
                    tmp['rate'] = str(round(int(classes.get('rate'))*8))
                    tmp['ceil'] = str(round(int(classes.get('ceil'))*8))
                    tmp['bytes'] = classes.get('stats', {}).get('bytes', 0)
                    tmp['packets'] = classes.get('stats', {}).get('packets', 0)
                    tmp['drops'] = classes.get('stats', {}).get('drops', 0)
                    tmp['queued'] = classes.get('stats', {}).get('backlog', 0)
                    tmp['overlimits'] = classes.get('stats', {}).get('overlimits', 0)
                    tmp['requeues'] = classes.get('stats', {}).get('requeues', 0)
                    tmp['lended'] = classes.get('stats', {}).get('lended', 0)
                    tmp['borrowed'] = classes.get('stats', {}).get('borrowed', 0)
                    tmp['giants'] = classes.get('stats', {}).get('giants', 0)

                    output_dict['classes'][class_name] = tmp
                    raw_dict['qos'][interface_name][class_name] = tmp

        # Skip printing of values for this interface. All interfaces will be returned in a single dictionary if 'raw' is called
        if raw:
            continue

        # Default class may be out of order in original JSON. This moves it to the end
        move_default = output_dict.get('classes', {}).pop('default', None)
        if move_default:
            output_dict.get('classes')['default'] = move_default

        # Create the tables for outputs
        for output in output_dict.get('classes'):
            data = output_dict.get('classes').get(output)

            # Add values for detailed (list view) output
            if detail:
                output_list.append([data['interface_name'],
                                    data['policy_name'],
                                    data['direction'],
                                    data['class_name'],
                                    data['queue_type'],
                                    data['rate'],
                                    data['ceil'],
                                    data['bytes'],
                                    data['packets'],
                                    data['drops'],
                                    data['queued'],
                                    data['overlimits'],
                                    data['requeues'],
                                    data['lended'],
                                    data['borrowed'],
                                    data['giants']]
                                    )
            # Add values for normal (table view) output
            else:
                output_list.append([data['class_name'],
                                    data['queue_type'],
                                    format_data_type(int(data['rate']), 'b'),
                                    format_data_type(int(data['ceil']), 'b'),
                                    format_data_type(int(data['bytes']), 'B'),
                                    data['packets'],
                                    data['drops'],
                                    data['queued']]
                                    )

        if output_list:
            if detail:
                # Headers for detailed (list view) output
                headers = ['Interface', 'Policy Name', 'Direction', 'Class', 'Type', 'Bandwidth', 'Max. BW', 'Bytes', 'Packets', 'Drops', 'Queued', 'Overlimit', 'Requeue', 'Lended', 'Borrowed', 'Giants']

                print('-' * 35)
                print(f"Interface: {interface_name}")
                print(f"Policy Name: {policy_name}\n")
                detailed_output(output_list, headers)
            else:
                # Headers for table output
                headers = ['Class', 'Type', 'Bandwidth', 'Max. BW', 'Bytes', 'Pkts', 'Drops', 'Queued']
                align = ('left','left','right','right','right','right','right','right')

                print('-' * 80)
                print(f"Interface: {interface_name}")
                print(f"Policy Name: {policy_name}\n")
                print(tabulate(output_list, headers, colalign=align))
                print(" \n")

    # Return dictionary with all interfaces if 'raw' is called
    if raw:
        return raw_dict

def show_cake(raw: bool, ifname: typing.Optional[str]):    
    if not interface_exists(ifname):
        raise vyos.opmode.Error(f"{ifname} does not exist!")
        
    cake_data = json.loads(cmd(f"tc -j -s qdisc show dev {ifname}"))[0]
    if cake_data:
        if cake_data.get('kind') == 'cake':
            if raw:
                return {'qos': {ifname: cake_data}}
            else:
                print(cmd(f"tc -s qdisc show dev {ifname}"))

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
