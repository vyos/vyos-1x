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

LWTUNNEL_ENCAP_NONE = 0
LWTUNNEL_ENCAP_MPLS = 1
LWTUNNEL_ENCAP_IP = 2
LWTUNNEL_ENCAP_ILA = 3
LWTUNNEL_ENCAP_IP6 = 4
LWTUNNEL_ENCAP_SEG6 = 5
LWTUNNEL_ENCAP_BPF = 6
LWTUNNEL_ENCAP_SEG6_LOCAL = 7
LWTUNNEL_ENCAP_RPL = 8
LWTUNNEL_ENCAP_IOAM6 = 9
LWTUNNEL_ENCAP_XFRM = 10

ENCAP_TO_NAME = {
    LWTUNNEL_ENCAP_MPLS: 'mpls',
    LWTUNNEL_ENCAP_IP: 'ip',
    LWTUNNEL_ENCAP_IP6: 'ip6',
    LWTUNNEL_ENCAP_ILA: 'ila',
    LWTUNNEL_ENCAP_BPF: 'bpf',
    LWTUNNEL_ENCAP_SEG6: 'seg6',
    LWTUNNEL_ENCAP_SEG6_LOCAL: 'seg6local',
    LWTUNNEL_ENCAP_RPL: 'rpl',
    LWTUNNEL_ENCAP_IOAM6: 'ioam6',
    LWTUNNEL_ENCAP_XFRM: 'xfrm',
}
