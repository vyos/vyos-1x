#!/usr/bin/env python3

import json
import argparse

from vyos.command import cmd

# [{"ifindex":1,"ifname":"lo","flags":["LOOPBACK","UP","LOWER_UP"],"mtu":65536,"qdisc":"noqueue","operstate":"UNKNOWN","group":"default","txqlen":1000,"link_type":"loopback","address":"00:00:00:00:00:00","broadcast":"00:00:00:00:00:00","addr_info":[{"family":"inet","local":"127.0.0.1","prefixlen":8,"scope":"host","label":"lo","valid_life_time":4294967295,"preferred_life_time":4294967295},{"family":"inet6","local":"::1","prefixlen":128,"scope":"host","valid_life_time":4294967295,"preferred_life_time":4294967295}]},{"ifindex":2,"ifname":"eth0","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":1500,"qdisc":"pfifo_fast","operstate":"UP","group":"default","txqlen":1000,"link_type":"ether","address":"08:00:27:fa:12:53","broadcast":"ff:ff:ff:ff:ff:ff","addr_info":[{"family":"inet","local":"10.0.2.15","prefixlen":24,"broadcast":"10.0.2.255","scope":"global","label":"eth0","valid_life_time":4294967295,"preferred_life_time":4294967295},{"family":"inet6","local":"fe80::a00:27ff:fefa:1253","prefixlen":64,"scope":"link","valid_life_time":4294967295,"preferred_life_time":4294967295}]},{"ifindex":3,"ifname":"eth1","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":1500,"qdisc":"pfifo_fast","operstate":"UP","group":"default","txqlen":1000,"link_type":"ether","address":"08:00:27:0d:25:dc","broadcast":"ff:ff:ff:ff:ff:ff","addr_info":[{"family":"inet6","local":"fe80::a00:27ff:fe0d:25dc","prefixlen":64,"scope":"link","valid_life_time":4294967295,"preferred_life_time":4294967295}]},{"ifindex":4,"ifname":"eth2","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":1500,"qdisc":"pfifo_fast","operstate":"UP","group":"default","txqlen":1000,"link_type":"ether","address":"08:00:27:68:d0:b1","broadcast":"ff:ff:ff:ff:ff:ff","addr_info":[{"family":"inet6","local":"fe80::a00:27ff:fe68:d0b1","prefixlen":64,"scope":"link","valid_life_time":4294967295,"preferred_life_time":4294967295}]},{"ifindex":5,"ifname":"eth3","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":1500,"qdisc":"pfifo_fast","operstate":"UP","group":"default","txqlen":1000,"link_type":"ether","address":"08:00:27:f0:17:c5","broadcast":"ff:ff:ff:ff:ff:ff","addr_info":[{"family":"inet6","local":"fe80::a00:27ff:fef0:17c5","prefixlen":64,"scope":"link","valid_life_time":4294967295,"preferred_life_time":4294967295}]}]

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()

    out = cmd('ip -j address show')
    data = json.loads(out)


    interfaces = []
    for interface in data:
        if not 'addr_info' in interface:
            continue
        interfaces.extend(interface['addr_info'])

    print(' '.join([interface['local'] for interface in interfaces if 'local' in interface]))
