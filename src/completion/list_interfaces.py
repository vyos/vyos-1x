#!/usr/bin/env python3

import sys
import argparse
import vyos.interfaces

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("-t", "--type", type=str, help="List interfaces of specific type")
group.add_argument("-b", "--broadcast", action="store_true", help="List all broadcast interfaces")
group.add_argument("-br", "--bridgeable", action="store_true", help="List all bridgeable interfaces")
group.add_argument("-bo", "--bondable", action="store_true", help="List all bondable interfaces")

args = parser.parse_args()

if args.type:
    try:
        interfaces = vyos.interfaces.list_interfaces_of_type(args.type)
        
    except ValueError as e:
        print(e, file=sys.stderr)
        print("")

elif args.broadcast:
    eth = vyos.interfaces.list_interfaces_of_type("ethernet")
    bridge = vyos.interfaces.list_interfaces_of_type("bridge")
    bond = vyos.interfaces.list_interfaces_of_type("bonding")
    interfaces = eth + bridge + bond

elif args.bridgeable:
    eth = vyos.interfaces.list_interfaces_of_type("ethernet")
    bond = vyos.interfaces.list_interfaces_of_type("bonding")
    l2tpv3 = vyos.interfaces.list_interfaces_of_type("l2tpv3")
    openvpn = vyos.interfaces.list_interfaces_of_type("openvpn")
    vxlan = vyos.interfaces.list_interfaces_of_type("vxlan")
    wireless = vyos.interfaces.list_interfaces_of_type("wireless")
    tunnel = vyos.interfaces.list_interfaces_of_type("tunnel")
    interfaces = eth + bond + l2tpv3 + openvpn + vxlan + wireless + tunnel

elif args.bondable:
    eth = vyos.interfaces.list_interfaces_of_type("ethernet")
    # we need to filter out VLAN interfaces identified by a dot (.) in their name
    for intf in eth:
        if '.' in intf:
            eth.remove(intf)
    interfaces = eth

else:
    interfaces = vyos.interfaces.list_interfaces()

print(" ".join(interfaces))
