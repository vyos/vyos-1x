#!/bin/sh

if [ -d "/sys/class/net/$1" ]; then
  /usr/sbin/pppstats "$1";
fi
