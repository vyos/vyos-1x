# Copyright 2019 VyOS maintainers and contributors <maintainers@vyos.io>
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


from vyos.ifconfig.interface import Interface

from vyos.ifconfig.bond import BondIf
from vyos.ifconfig.bridge import BridgeIf
from vyos.ifconfig.dummy import DummyIf
from vyos.ifconfig.ethernet import EthernetIf
from vyos.ifconfig.geneve import GeneveIf
from vyos.ifconfig.loopback import LoopbackIf
from vyos.ifconfig.macvlan import MACVLANIf
from vyos.ifconfig.stp import STPIf
from vyos.ifconfig.vlan import VLANIf
from vyos.ifconfig.vxlan import VXLANIf
from vyos.ifconfig.wireguard import WireGuardIf
