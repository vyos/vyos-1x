#!/usr/bin/env bash
#
# Copyright (C) 2020 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

target=$1
interface=$2

# IPv4 header 20 byte + TCP header 20 byte
ipv4_overhead=40

# IPv6 headter 40 byte + TCP header 20 byte
ipv6_overhead=60

# If no arguments
if [[ $# -eq 0 ]] ; then
    echo "Target host not defined"
    exit 1
fi

# If one argument, it's ip address. If 2, the second arg "interface"
if [[ $# -eq 1 ]] ; then
    mtu=$(sudo nmap -T4 --script path-mtu -F $target | grep "PMTU" | awk {'print $NF'})
elif [[ $# -eq 2 ]]; then
    mtu=$(sudo nmap -T4 -e $interface --script path-mtu -F $target | grep "PMTU" | awk {'print $NF'})
fi

tcpv4_mss=$(($mtu-$ipv4_overhead))
tcpv6_mss=$(($mtu-$ipv6_overhead))

echo "
Recommended maximum values (or less) for target $target:
---
MTU:     $mtu
TCP-MSS: $tcpv4_mss
TCP-MSS_IPv6: $tcpv6_mss
"

