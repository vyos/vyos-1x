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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import typing
import json
from tabulate import tabulate

import vyos.opmode
from vyos.utils.process import cmd
from vyos.utils.network import interface_exists

def detailed_output(dataset, headers):
    for data in dataset:
        adjusted_rule = data + [""] * (len(headers) - len(data)) # account for different header length, like default-action
        transformed_rule = [[header, adjusted_rule[i]] for i, header in enumerate(headers) if i < len(adjusted_rule)] # create key-pair list from headers and rules lists; wrap at 100 char

        print(tabulate(transformed_rule, tablefmt="presto"))
        print()

def _get_bridge_vlan_data(iface):
    allowed_vlans = []
    native_vlan = None
    vlanData = json.loads(cmd(f"bridge -j -d vlan show"))
    for vlans in vlanData:
        if vlans['ifname'] == iface:
            for allowed in vlans['vlans']:
                if "flags" in allowed and "PVID" in allowed["flags"]:
                    native_vlan = allowed['vlan']
                elif allowed.get('vlanEnd', None):
                    allowed_vlans.append(f"{allowed['vlan']}-{allowed['vlanEnd']}")
                else:
                    allowed_vlans.append(str(allowed['vlan']))

    if not allowed_vlans:
        allowed_vlans = ["none"]
    if not native_vlan:
        native_vlan = "none"

    return ",".join(allowed_vlans), native_vlan

def _get_stp_data(ifname, brInfo, brStatus):
    tmpInfo = {}

    tmpInfo['bridge_name'] = brInfo.get('ifname')
    tmpInfo['up_state'] = brInfo.get('operstate')
    tmpInfo['priority'] = brInfo.get('linkinfo').get('info_data').get('priority')
    tmpInfo['vlan_filtering'] = "Enabled" if brInfo.get('linkinfo').get('info_data').get('vlan_filtering') == 1 else "Disabled"
    tmpInfo['vlan_protocol'] = brInfo.get('linkinfo').get('info_data').get('vlan_protocol')

    # The version of VyOS I tested had am issue with the "ip -d link show type bridge"
    # output. The root_id was always the local bridge, even though the underlying system
    # understood when it wasn't. Could be an upstream Bug. I pull from the "/sys/class/net"
    # structure instead. This can be changed later if the "ip link" behavior is corrected.

    #tmpInfo['bridge_id'] = brInfo.get('linkinfo').get('info_data').get('bridge_id')
    #tmpInfo['root_id'] = brInfo.get('linkinfo').get('info_data').get('root_id')

    tmpInfo['bridge_id'] = cmd(f"cat /sys/class/net/{brInfo.get('ifname')}/bridge/bridge_id").split('.')
    tmpInfo['root_id'] = cmd(f"cat /sys/class/net/{brInfo.get('ifname')}/bridge/root_id").split('.')

    # The "/sys/class/net" structure stores the IDs without seperators like ':' or '.'
    # This adds a ':' after every 2 characters to make it resemble a MAC Address
    tmpInfo['bridge_id'][1] = ':'.join(tmpInfo['bridge_id'][1][i:i+2] for i in range(0, len(tmpInfo['bridge_id'][1]), 2))
    tmpInfo['root_id'][1] = ':'.join(tmpInfo['root_id'][1][i:i+2] for i in range(0, len(tmpInfo['root_id'][1]), 2))

    tmpInfo['stp_state'] = "Enabled" if brInfo.get('linkinfo', {}).get('info_data', {}).get('stp_state') == 1 else "Disabled"

    # I don't call any of these values, but I created them to be called within raw output if desired

    tmpInfo['mcast_snooping'] = "Enabled" if brInfo.get('linkinfo').get('info_data').get('mcast_snooping') == 1 else "Disabled"
    tmpInfo['rxbytes'] = brInfo.get('stats64').get('rx').get('bytes')
    tmpInfo['rxpackets'] = brInfo.get('stats64').get('rx').get('packets')
    tmpInfo['rxerrors'] = brInfo.get('stats64').get('rx').get('errors')
    tmpInfo['rxdropped'] = brInfo.get('stats64').get('rx').get('dropped')
    tmpInfo['rxover_errors'] = brInfo.get('stats64').get('rx').get('over_errors')
    tmpInfo['rxmulticast'] = brInfo.get('stats64').get('rx').get('multicast')
    tmpInfo['txbytes'] = brInfo.get('stats64').get('tx').get('bytes')
    tmpInfo['txpackets'] = brInfo.get('stats64').get('tx').get('packets')
    tmpInfo['txerrors'] = brInfo.get('stats64').get('tx').get('errors')
    tmpInfo['txdropped'] = brInfo.get('stats64').get('tx').get('dropped')
    tmpInfo['txcarrier_errors'] = brInfo.get('stats64').get('tx').get('carrier_errors')
    tmpInfo['txcollosions'] = brInfo.get('stats64').get('tx').get('collisions')

    tmpStatus = []
    for members in brStatus:
        if members.get('master') == brInfo.get('ifname'):
            allowed_vlans, native_vlan = _get_bridge_vlan_data(members['ifname'])
            tmpStatus.append({'interface': members.get('ifname'),
                                'state': members.get('state').capitalize(),
                                'mtu': members.get('mtu'),
                                'pathcost': members.get('cost'),
                                'bpduguard': "Enabled" if members.get('guard') == True else "Disabled",
                                'rootguard': "Enabled" if members.get('root_block') == True else "Disabled",
                                'mac_learning': "Enabled" if members.get('learning') == True else "Disabled",
                                'neigh_suppress': "Enabled" if members.get('neigh_suppress') == True else "Disabled",
                                'vlan_tunnel': "Enabled" if members.get('vlan_tunnel') == True else "Disabled",
                                'isolated': "Enabled" if members.get('isolated') == True else "Disabled",
                                **({'allowed_vlans': allowed_vlans} if allowed_vlans else {}),
                                **({'native_vlan': native_vlan} if native_vlan else {})})

    tmpInfo['members'] = tmpStatus
    return tmpInfo

def show_stp(raw: bool, ifname: typing.Optional[str], detail: bool):
    rawList = []
    rawDict = {'stp': []}

    if ifname:
        if not interface_exists(ifname):
            raise vyos.opmode.Error(f"{ifname} does not exist!")
    else:
        ifname = ""

    bridgeInfo = json.loads(cmd(f"ip -j -d -s link show type bridge {ifname}"))

    if not bridgeInfo:
        raise vyos.opmode.Error(f"No Bridges configured!")

    bridgeStatus = json.loads(cmd(f"bridge -j -s -d link show"))

    for bridges in bridgeInfo:
        output_list = []
        amRoot = ""
        bridgeDict = _get_stp_data(ifname, bridges, bridgeStatus)

        if bridgeDict['bridge_id'][1] == bridgeDict['root_id'][1]:
            amRoot = " (This bridge is the root)"

        print('-' * 80)
        print(f"Bridge interface {bridgeDict['bridge_name']} ({bridgeDict['up_state']}):\n")
        print(f"Spanning Tree is {bridgeDict['stp_state']}")
        print(f"Bridge ID {bridgeDict['bridge_id'][1]}, Priority {int(bridgeDict['bridge_id'][0], 16)}")
        print(f"Root ID {bridgeDict['root_id'][1]}, Priority {int(bridgeDict['root_id'][0], 16)}{amRoot}")
        print(f"VLANs {bridgeDict['vlan_filtering'].capitalize()}, Protocol {bridgeDict['vlan_protocol']}")
        print()

        for members in bridgeDict['members']:
            output_list.append([members['interface'],
                              members['state'],
                              *([members['pathcost']] if detail else []),
                              members['bpduguard'],
                              members['rootguard'],
                              members['mac_learning'],
                              *([members['neigh_suppress']] if detail else []),
                              *([members['vlan_tunnel']] if detail else []),
                              *([members['isolated']] if detail else []),
                              *([members['allowed_vlans']] if detail else []),
                              *([members['native_vlan']] if detail else [])])

        if raw:
            rawList.append(bridgeDict)
        elif detail:
            headers = ['Interface', 'State', 'Pathcost', 'BPDU_Guard', 'Root_Guard', 'Learning', 'Neighbor_Suppression', 'Q-in-Q', 'Port_Isolation', 'Allowed VLANs', 'Native VLAN']
            detailed_output(output_list, headers)
        else:
            headers = ['Interface', 'State', 'BPDU_Guard', 'Root_Guard', 'Learning']
            print(tabulate(output_list, headers))
            print()

    if raw:
        rawDict['stp'] = rawList
        return rawDict

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
