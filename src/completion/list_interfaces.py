#!/usr/bin/env python3

import sys
import argparse
from vyos.ifconfig import Section

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
        interfaces = Section.interfaces(args.type)

    except ValueError as e:
        print(e, file=sys.stderr)
        print("")

elif args.broadcast:
    eth = Section.interfaces("ethernet")
    bridge = Section.interfaces("bridge")
    bond = Section.interfaces("bonding")
    interfaces = eth + bridge + bond

elif args.bridgeable:
    eth = Section.interfaces("ethernet")
    bond = Section.interfaces("bonding")
    l2tpv3 = Section.interfaces("l2tpv3")
    openvpn = Section.interfaces("openvpn")
    wireless = Section.interfaces("wireless")
    tunnel = Section.interfaces("tunnel")
    vxlan = Section.interfaces("vxlan")
    geneve = Section.interfaces("geneve")

    interfaces = eth + bond + l2tpv3 + openvpn + vxlan + tunnel + wireless + geneve

elif args.bondable:
    interfaces = []
    eth = Section.interfaces("ethernet")

    # we need to filter out VLAN interfaces identified by a dot (.) in their name
    for intf in eth:
        if not '.' in intf:
            interfaces.append(intf)

else:
    interfaces = Section.interfaces()

print(" ".join(interfaces))
