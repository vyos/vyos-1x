#!/bin/sh
# Copyright (C) 2021-2022 VyOS maintainers and contributors
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

# Return BGP neighbor addresses from CLI, can either request IPv4 only, IPv6
# only or both address-family neighbors

ipv4=0
ipv6=0
vrf=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -4|--ipv4) ipv4=1 ;;
        -6|--ipv6) ipv6=1 ;;
        -b|--both) ipv4=1; ipv6=1 ;;
        --vrf) vrf="vrf name $2"; shift ;;
        *) echo "Unknown parameter passed: $1" ;;
    esac
    shift
done

declare -a vals
eval "vals=($(cli-shell-api listActiveNodes $vrf protocols bgp neighbor))"

if [ $ipv4 -eq 1 ] && [ $ipv6 -eq 1 ]; then
    echo -n '<x.x.x.x>' '<h:h:h:h:h:h:h:h>' ${vals[@]}
elif [ $ipv4 -eq 1 ] ; then
     echo -n '<x.x.x.x> '
     for peer in "${vals[@]}"
     do
        ipaddrcheck --is-ipv4-single $peer
        if [ $? -eq "0" ]; then
            echo -n "$peer "
        fi
     done
elif [ $ipv6 -eq 1 ] ; then
    echo -n '<h:h:h:h:h:h:h:h> '
     for peer in "${vals[@]}"
     do
        ipaddrcheck --is-ipv6-single $peer
        if [ $? -eq "0" ]; then
            echo -n "$peer "
        fi
     done
else
    echo "Usage:"
    echo "-4|--ipv4      list only IPv4 peers"
    echo "-6|--ipv6      list only IPv6 peers"
    echo "--both         list both IP4 and IPv6 peers"
    echo "--vrf <name>   apply command to given VRF (optional)"
    echo ""
    exit 1
fi

exit 0
