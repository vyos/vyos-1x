#!/bin/sh

if [ -d /etc/ppp/peers ]; then
    cd /etc/ppp/peers
    ls wlm*
fi
