#!/bin/sh

if [ -f "/proc/net/bonding/$1" ]; then
  cat "/proc/net/bonding/$1";
else
  echo "Interface $1 does not exist!";
fi
