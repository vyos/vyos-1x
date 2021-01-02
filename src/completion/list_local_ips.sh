#!/bin/sh

ipv4=0
ipv6=0

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -4|--ipv4) ipv4=1 ;;
        -6|--ipv6) ipv6=1 ;;
        -b|--both) ipv4=1; ipv6=1 ;;
        *) echo "Unknown parameter passed: $1" ;;
    esac
    shift
done

if [ $ipv4 -eq 1 ] && [ $ipv6 -eq 1 ]; then
    ip a | grep inet | awk '{print $2}' | sed -e /^fe80::/d | awk -F/ '{print $1}' | sort -u
elif [ $ipv4 -eq 1 ] ; then
    ip a | grep 'inet ' | awk '{print $2}' | awk -F/ '{print $1}' | sort -u
elif [ $ipv6 -eq 1 ] ; then
    ip a | grep 'inet6 ' | awk '{print $2}' | sed -e /^fe80::/d | awk -F/ '{print $1}' | sort -u
else
    echo "Usage:"
    echo "-4|--ipv4    list only IPv4 addresses"
    echo "-6|--ipv6    list only IPv6 addresses"
    echo "--both       list both IP4 and IPv6 addresses"
    echo ""
    exit 1
fi
