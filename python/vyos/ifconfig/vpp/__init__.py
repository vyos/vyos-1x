#
# Copyright (C) VyOS Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from .bond import VPPBondInterface
from .bridge import VPPBridgeInterface
from .gre import VPPGREInterface
from .interface import VPPInterface
from .ipip import VPPIPIPInterface
from .loopback import VPPLoopbackInterface
from .vxlan import VPPVXLANInterface
from .xconnect import VPPXconnectInterface

__all__ = [
    'VPPBondInterface',
    'VPPBridgeInterface',
    'VPPGREInterface',
    'VPPInterface',
    'VPPIPIPInterface',
    'VPPLoopbackInterface',
    'VPPVXLANInterface',
    'VPPXconnectInterface',
]
