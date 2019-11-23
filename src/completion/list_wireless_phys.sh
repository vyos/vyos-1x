#!/bin/sh

if [ -d /sys/class/ieee80211 ]; then
    ls -x /sys/class/ieee80211
fi
