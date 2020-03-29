#!/usr/bin/env python3

import sys
import argparse
from vyos.ifconfig import Interface

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("-t", "--type", type=str, help="List interfaces of specific type")
group.add_argument("-b", "--broadcast", action="store_true", help="List all broadcast interfaces")
group.add_argument("-br", "--bridgeable", action="store_true", help="List all bridgeable interfaces")
group.add_argument("-bo", "--bondable", action="store_true", help="List all bondable interfaces")

args = parser.parse_args()

# XXX: Need to be rewritten using the data in the class definition
# XXX: It can be done once vti and input are moved into vyos
# XXX: We store for each class what type they are (broadcast, bridgeabe, ...)

if args.type:
    try:
        interfaces = Interface.listing(args.type)

    except ValueError as e:
        print(e, file=sys.stderr)
        print("")

elif args.broadcast:
    eth = Interface.listing("ethernet")
    bridge = Interface.listing("bridge")
    bond = Interface.listing("bonding")
    interfaces = eth + bridge + bond

elif args.bridgeable:
    eth = Interface.listing("ethernet")
    bond = Interface.listing("bonding")
    l2tpv3 = Interface.listing("l2tpv3")
    openvpn = Interface.listing("openvpn")
    wireless = Interface.listing("wireless")
    tunnel = Interface.listing("tunnel")
    vxlan = Interface.listing("vxlan")
    geneve = Interface.listing("geneve")

    interfaces = eth + bond + l2tpv3 + openvpn + vxlan + tunnel + wireless + geneve

elif args.bondable:
    interfaces = []
    eth = Interface.listing("ethernet")

    # we need to filter out VLAN interfaces identified by a dot (.) in their name
    for intf in eth:
        if not '.' in intf:
            interfaces.append(intf)

else:
    interfaces = Interface.listing()

print(" ".join(interfaces))
