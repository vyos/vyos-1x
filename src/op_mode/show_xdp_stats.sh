#!/bin/sh

if cli-shell-api existsEffective interfaces $1 $2 xdp; then
    /usr/sbin/xdp_stats --dev "$2"
else
    echo "XDP not enabled on $2"
fi
