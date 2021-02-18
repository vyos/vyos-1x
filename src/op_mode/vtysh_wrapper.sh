#!/bin/sh
declare -a tmp
tmp=$@
vtysh -c "$tmp"
