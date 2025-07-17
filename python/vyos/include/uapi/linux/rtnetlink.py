# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

RTM_F_NOTIFY = 0x100
RTM_F_CLONED = 0x200
RTM_F_EQUALIZE = 0x400
RTM_F_PREFIX = 0x800
RTM_F_LOOKUP_TABLE = 0x1000
RTM_F_FIB_MATCH = 0x2000
RTM_F_OFFLOAD = 0x4000
RTM_F_TRAP = 0x8000
RTM_F_OFFLOAD_FAILED = 0x20000000

RTNH_F_DEAD = 1
RTNH_F_PERVASIVE = 2
RTNH_F_ONLINK = 4
RTNH_F_OFFLOAD = 8
RTNH_F_LINKDOWN = 16
RTNH_F_UNRESOLVED = 32
RTNH_F_TRAP = 64

RT_TABLE_COMPAT = 252
RT_TABLE_DEFAULT = 253
RT_TABLE_MAIN = 254
RT_TABLE_LOCAL = 255

RTAX_FEATURE_ECN = (1 << 0)
RTAX_FEATURE_SACK = (1 << 1)
RTAX_FEATURE_TIMESTAMP = (1 << 2)
RTAX_FEATURE_ALLFRAG = (1 << 3)
RTAX_FEATURE_TCP_USEC_TS = (1 << 4)

RT_FlAGS = {
    'dead': RTNH_F_DEAD,
    'onlink': RTNH_F_ONLINK,
    'pervasive':  RTNH_F_PERVASIVE,
    'offload': RTNH_F_OFFLOAD,
    'trap': RTNH_F_TRAP,
    'notify': RTM_F_NOTIFY,
    'linkdown': RTNH_F_LINKDOWN,
    'unresolved': RTNH_F_UNRESOLVED,
    'rt_offload': RTM_F_OFFLOAD,
    'rt_trap': RTM_F_TRAP,
    'rt_offload_failed': RTM_F_OFFLOAD_FAILED,
}

RT_TABLE_TO_NAME = {
    RT_TABLE_COMPAT: 'compat',
    RT_TABLE_DEFAULT: 'default',
    RT_TABLE_MAIN: 'main',
    RT_TABLE_LOCAL: 'local',
}
