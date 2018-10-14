#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#

import sys

import vyos.config

if len(sys.argv) < 2:
    print("Argument (bridge interface name) is required")
    sys.exit(1)
else:
    bridge = sys.argv[1]

c = vyos.config.Config()

members = []


# Check in ethernet and bonding interfaces
for p in ["interfaces ethernet", "interfaces bonding"]:
    intfs = c.list_nodes(p)
    for i in intfs:
        intf_bridge_path = "{0} {1} bridge-group bridge".format(p, i)
        if c.exists(intf_bridge_path):
            intf_bridge = c.return_value(intf_bridge_path)
            if intf_bridge == bridge:
                members.append(i)
        # Walk VLANs
        for v in c.list_nodes("{0} {1} vif".format(p, i)):
            vif_bridge_path = "{0} {1} vif {2} bridge-group bridge".format(p, i, v)
            if c.exists(vif_bridge_path):
                vif_bridge = c.return_value(vif_bridge_path)
                if vif_bridge == bridge:
                    members.append("{0}.{1}".format(i, v))
        # Walk QinQ interfaces
        for vs in c.list_nodes("{0} {1} vif-s".format(p, i)):
            vifs_bridge_path = "{0} {1} vif-s {2} bridge-group bridge".format(p, i, vs)
            if c.exists(vifs_bridge_path):
                vifs_bridge = c.return_value(vifs_bridge_path)
                if vifs_bridge == bridge:
                    members.append("{0}.{1}".format(i, vs))
            for vc in c.list_nodes("{0} {1} vif-s {2} vif-c".format(p, i, vs)):
                vifc_bridge_path = "{0} {1} vif-s {2} vif-c {3} bridge-group bridge".format(p, i, vs, vc)
                if c.exists(vifc_bridge_path):
                    vifc_bridge = c.return_value(vifc_bridge_path)
                    if vifc_bridge == bridge:
                        members.append("{0}.{1}.{2}".format(i, vs, vc))

# Check tunnel interfaces
for t in c.list_nodes("interfaces tunnel"):
    tunnel_bridge_path = "interfaces tunnel {0} parameters ip bridge-group bridge".format(t)
    if c.exists(tunnel_bridge_path):
        intf_bridge = c.return_value(tunnel_bridge_path)
        if intf_bridge == bridge:
            members.append(t)

# Check OpenVPN interfaces
for o in c.list_nodes("interfaces openvpn"):
    ovpn_bridge_path = "interfaces openvpn {0} bridge-group bridge".format(o)
    if c.exists(ovpn_bridge_path):
        intf_bridge = c.return_value(ovpn_bridge_path)
        if intf_bridge == bridge:
            members.append(o)

if members:
    print("Bridge {0} cannot be deleted because some interfaces are configured as its members".format(bridge))
    print("The following interfaces are members of {0}: {1}".format(bridge, " ".join(members)))
    sys.exit(1)
else:
    sys.exit(0)
