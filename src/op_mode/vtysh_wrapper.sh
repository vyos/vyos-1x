#!/bin/sh
declare -a tmp
# FRR uses ospf6 where we use ospfv3, thus alter the command
tmp=$(echo $@ | sed -e "s/ospfv3/ospf6/")
vtysh -c "$tmp"
