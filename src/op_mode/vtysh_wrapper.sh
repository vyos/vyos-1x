#!/bin/sh
declare -a tmp
# FRR uses ospf6 where we use ospfv3, and we use reset over clear for BGP,
# thus alter the commands
tmp=$(echo $@ | sed -e "s/ospfv3/ospf6/" | sed -e "s/^reset bgp/clear bgp/" | sed -e "s/^reset ip bgp/clear ip bgp/")
vtysh -c "$tmp"
