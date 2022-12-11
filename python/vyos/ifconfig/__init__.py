# Copyright 2019-2022 VyOS maintainers and contributors <maintainers@vyos.io>
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

from vyos.ifconfig.section import Section
from vyos.ifconfig.control import Control
from vyos.ifconfig.interface import Interface
from vyos.ifconfig.operational import Operational
from vyos.ifconfig.vrrp import VRRP

from vyos.ifconfig.bond import BondIf
from vyos.ifconfig.bridge import BridgeIf
from vyos.ifconfig.dummy import DummyIf
from vyos.ifconfig.ethernet import EthernetIf
from vyos.ifconfig.geneve import GeneveIf
from vyos.ifconfig.loopback import LoopbackIf
from vyos.ifconfig.macvlan import MACVLANIf
from vyos.ifconfig.input import InputIf
from vyos.ifconfig.vxlan import VXLANIf
from vyos.ifconfig.wireguard import WireGuardIf
from vyos.ifconfig.vtun import VTunIf
from vyos.ifconfig.vti import VTIIf
from vyos.ifconfig.pppoe import PPPoEIf
from vyos.ifconfig.tunnel import TunnelIf
from vyos.ifconfig.wireless import WiFiIf
from vyos.ifconfig.l2tpv3 import L2TPv3If
from vyos.ifconfig.macsec import MACsecIf
from vyos.ifconfig.veth import VethIf
from vyos.ifconfig.wwan import WWANIf
from vyos.ifconfig.sstpc import SSTPCIf
