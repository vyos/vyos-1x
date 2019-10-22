# Copyright 2018 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import re
import json

import subprocess
import netifaces

intf_type_data_file = '/usr/share/vyos/interface-types.json'

def list_interfaces():
    interfaces = netifaces.interfaces()

    # Remove "fake" interfaces associated with drivers
    for i in ["dummy0", "ip6tnl0", "tunl0", "ip_vti0", "ip6_vti0"]:
        try:
            interfaces.remove(i)
        except ValueError:
            pass

    return interfaces

def list_interfaces_of_type(typ):
    with open(intf_type_data_file, 'r') as f:
        types_data = json.load(f)

    all_intfs = list_interfaces()
    if not (typ in types_data.keys()):
        raise ValueError("Unknown interface type: {0}".format(typ))
    else:
        r = re.compile('^{0}\d+'.format(types_data[typ]))
        return list(filter(lambda i: re.match(r, i), all_intfs))

def get_type_of_interface(intf):
    with open(intf_type_data_file, 'r') as f:
        types_data = json.load(f)

    for key,val in types_data.items():
        r = re.compile('^{0}\d+'.format(val))
        if re.match(r, intf):
            return key

    raise ValueError("No type found for interface name: {0}".format(intf))

def wireguard_dump():
    """Dump wireguard data in a python friendly way."""
    last_device=None
    output = {}
    
    # Dump wireguard connection data
    _f = subprocess.check_output(["wg", "show", "all", "dump"]).decode()
    for line in _f.split('\n'):
        if not line:
          # Skip empty lines and last line
          continue
        items = line.split('\t')

        if last_device != items[0]:
            # We are currently entering a new node
            device, private_key, public_key, listen_port, fw_mark = items
            last_device = device
            
            output[device] = {
                'private_key': None if private_key == '(none)' else private_key,
                'public_key': None if public_key == '(none)' else public_key,
                'listen_port': int(listen_port),
                'fw_mark': None if fw_mark == 'off' else int(fw_mark),
                'peers': {},
                } 
        else:
            # We are entering a peer
            device, public_key, preshared_key, endpoint, allowed_ips, latest_handshake, transfer_rx, transfer_tx, persistent_keepalive = items
            if allowed_ips == '(none)':
                allowed_ips = []
            else:
                allowed_ips = allowed_ips.split('\t')
            output[device]['peers'][public_key] = {
                'preshared_key': None if preshared_key == '(none)' else preshared_key,
                'endpoint': None if endpoint == '(none)' else endpoint,
                'allowed_ips': allowed_ips,
                'latest_handshake': None if latest_handshake == '0' else int(latest_handshake),
                'transfer_rx': int(transfer_rx),
                'transfer_tx': int(transfer_tx),
                'persistent_keepalive': None if persistent_keepalive == 'off' else int(persistent_keepalive),
           } 
    return output
