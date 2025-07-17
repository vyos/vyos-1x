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

NTF_USE = (1 << 0)
NTF_SELF = (1 << 1)
NTF_MASTER = (1 << 2)
NTF_PROXY = (1 << 3)
NTF_EXT_LEARNED = (1 << 4)
NTF_OFFLOADED = (1 << 5)
NTF_STICKY = (1 << 6)
NTF_ROUTER = (1 << 7)
NTF_EXT_MANAGED = (1 << 0)
NTF_EXT_LOCKED = (1 << 1)

NTF_FlAGS = {
    'self': NTF_SELF,
    'router': NTF_ROUTER,
    'extern_learn': NTF_EXT_LEARNED,
    'offload': NTF_OFFLOADED,
    'master': NTF_MASTER,
    'sticky': NTF_STICKY,
    'locked': NTF_EXT_LOCKED,
}
