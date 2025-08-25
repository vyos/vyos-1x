#!/usr/bin/env python3
#
# Copyright (C) VyOS Inc.
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

from vyos.configquery import ConfigTreeQuery

from vyos.vpp import VPPControl
from vyos.vpp.utils import vpp_ifaces_list


def get_vpp_ifaces_names():
    config = ConfigTreeQuery()
    if not config.exists('vpp settings interface'):
        return []

    vpp = VPPControl()
    vpp_ifaces = vpp_ifaces_list(vpp.api)
    ifaces_names = [iface['interface_name'] for iface in vpp_ifaces]

    return sorted(ifaces_names)


if __name__ == "__main__":
    ifaces = []
    ifaces = get_vpp_ifaces_names()
    print(" ".join(ifaces))
