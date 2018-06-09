#!/usr/bin/env python3

import sys
import argparse

import vyos.interfaces


parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("-t", "--type", type=str, help="List interfaces of specific type")
group.add_argument("-b", "--broadcast", action="store_true", help="List all broadcast interfaces")

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
else:
    interfaces = vyos.interfaces.list_interfaces()

print(" ".join(interfaces))
