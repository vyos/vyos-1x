#!/usr/bin/env python3

import argparse
import vyos.vrf

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("-e", "--extensive", action="store_true",
                   help="provide detailed vrf informatio")
parser.add_argument('interface', metavar='I', type=str, nargs='?',
                    help='interface to display')

args = parser.parse_args()

if args.extensive:
    print('{:16}  {:7}  {:17}  {}'.format('interface', 'state', 'mac', 'flags'))
    print('{:16}  {:7}  {:17}  {}'.format('---------', '-----', '---', '-----'))
    for vrf in vyos.vrf.list_vrfs():
        name = vrf['ifname']
        if args.interface and name != args.interface:
            continue
        state = vrf['operstate'].lower()
        mac = vrf['address'].lower()
        info = ','.join([_.lower() for _ in vrf['flags']])
        print(f'{name:16}  {state:7}  {mac:17}  {info}')
else:
    print(" ".join([vrf['ifname'] for vrf in vyos.vrf.list_vrfs()]))
