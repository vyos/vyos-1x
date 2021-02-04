#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

#ip -j -f inet neigh list | jq
#[
  #{
    #"dst": "192.168.101.8",
    #"dev": "enp0s25",
    #"lladdr": "78:d2:94:72:77:7e",
    #"state": [
      #"STALE"
    #]
  #},
  #{
    #"dst": "192.168.101.185",
    #"dev": "enp0s25",
    #"lladdr": "34:46:ec:76:f8:9b",
    #"state": [
      #"STALE"
    #]
  #},
  #{
    #"dst": "192.168.101.225",
    #"dev": "enp0s25",
    #"lladdr": "c2:cb:fa:bf:a0:35",
    #"state": [
      #"STALE"
    #]
  #},
  #{
    #"dst": "192.168.101.1",
    #"dev": "enp0s25",
    #"lladdr": "00:98:2b:f8:3f:11",
    #"state": [
      #"REACHABLE"
    #]
  #},
  #{
    #"dst": "192.168.101.181",
    #"dev": "enp0s25",
    #"lladdr": "d8:9b:3b:d5:88:22",
    #"state": [
      #"STALE"
    #]
  #}
#]

import sys
import argparse
import json
from vyos.util import cmd

def main():
    #parese args
    parser = argparse.ArgumentParser()
    parser.add_argument('--family', help='Protocol family', required=True)
    args = parser.parse_args()
    
    neigh_raw_json = cmd(f'ip -j -f {args.family} neigh list')
    neigh_raw_json = neigh_raw_json.lower()
    neigh_json = json.loads(neigh_raw_json)
    
    format_neigh = '%-50s %-10s %-20s %s'
    print(format_neigh % ("IP Address", "Device", "State", "LLADDR"))
    print(format_neigh % ("----------", "------", "-----", "------"))
    
    if neigh_json is not None:
        for neigh_item in neigh_json:
            dev = neigh_item['dev']
            dst = neigh_item['dst']
            lladdr = neigh_item['lladdr'] if 'lladdr' in neigh_item else ''
            state = neigh_item['state']
            
            i = 0
            for state_item in  state:
                if i == 0:
                    print(format_neigh % (dst, dev, state_item, lladdr))
                else:
                    print(format_neigh % ('', '', state_item, ''))
                i+=1
            
if __name__ == '__main__':
    main()
