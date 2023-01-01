# Copyright 2022 VyOS maintainers and contributors <maintainers@vyos.io>
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

from vyos.qos.base import QoSBase
from vyos.qos.cake import CAKE
from vyos.qos.droptail import DropTail
from vyos.qos.fairqueue import FairQueue
from vyos.qos.fqcodel import FQCodel
from vyos.qos.limiter import Limiter
from vyos.qos.netem import NetEm
from vyos.qos.priority import Priority
from vyos.qos.randomdetect import RandomDetect
from vyos.qos.ratelimiter import RateLimiter
from vyos.qos.roundrobin import RoundRobin
from vyos.qos.trafficshaper import TrafficShaper
from vyos.qos.trafficshaper import TrafficShaperHFSC
