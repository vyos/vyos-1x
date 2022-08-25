#!/usr/bin/env python3

from vyos.ifconfig import Section
from vyos.ifconfig import Interface

import time

def get_interface_addresses(iface, link_local_v6=False):
    """
    Get IP and IPv6 addresses from interface in one string
    By default don't get IPv6 link-local addresses
    If interface doesn't have address, return "-"
    """
    addresses = []
    addrs = Interface(iface).get_addr()

    for addr in addrs:
        if link_local_v6 == False:
            if addr.startswith('fe80::'):
                continue
        addresses.append(addr)

    if not addresses:
        return "-"

    return (" ".join(addresses))

def get_interface_description(iface):
    """
    Get interface description
    If none return "empty"
    """
    description = Interface(iface).get_alias()

    if not description:
        return "empty"

    return description

def get_interface_admin_state(iface):
    """
    Interface administrative state
    up => 0, down => 2
    """
    state = Interface(iface).get_admin_state()
    if state == 'up':
        admin_state = 0
    if state == 'down':
        admin_state = 2

    return admin_state

def get_interface_oper_state(iface):
    """
    Interface operational state
    up => 0, down => 1
    """
    state = Interface(iface).operational.get_state()
    if state == 'down':
        oper_state = 1
    else:
        oper_state = 0

    return oper_state

interfaces = Section.interfaces('')

for iface in interfaces:
    print(f'show_interfaces,interface={iface} '
          f'ip_addresses="{get_interface_addresses(iface)}",'
          f'state={get_interface_admin_state(iface)}i,'
          f'link={get_interface_oper_state(iface)}i,'
          f'description="{get_interface_description(iface)}" '
          f'{str(int(time.time()))}000000000')
