#!/usr/bin/env python3

import subprocess
import time

def status_to_int(status):
    switcher={
        'u':'0',
        'D':'1',
        'A':'2'
        }
    return switcher.get(status,"")

def description_check(line):
    desc=" ".join(line[3:])
    if desc == "":
        return "empty"
    else:
        return desc

def gen_ip_list(index,interfaces):
    line=interfaces[index].split()
    ip_list=line[1]
    if index < len(interfaces):
        index += 1
        while len(interfaces[index].split())==1:
            ip = interfaces[index].split()
            ip_list = ip_list + " " + ip[0]
            index += 1
            if index == len(interfaces):
                break
    return ip_list

interfaces = subprocess.check_output("/usr/libexec/vyos/op_mode/show_interfaces.py --action=show-brief", shell=True).decode('utf-8').splitlines()
del interfaces[:3]
lines_count=len(interfaces)
index=0
while index<lines_count:
    line=interfaces[index].split()
    if len(line)>1:
        print(f'show_interfaces,interface={line[0]} '
              f'ip_addresses="{gen_ip_list(index,interfaces)}",'
              f'state={status_to_int(line[2][0])}i,'
              f'link={status_to_int(line[2][2])}i,'
              f'description="{description_check(line)}" '
              f'{str(int(time.time()))}000000000')
    index += 1
