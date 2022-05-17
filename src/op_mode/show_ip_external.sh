#!/usr/bin/env bash

# Detect an external IP address
# Use random services for checking


array=(
    ipinfo.io/ip
    ifconfig.me
    ipecho.net/plain
    icanhazip.com
    v4.ident.me
    checkip.amazonaws.com
)

size=${#array[@]}
index=$(($RANDOM % $size))

curl --silent ${array[$index]} | tr -d "[:space:]" && echo
