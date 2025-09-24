#!/bin/bash

INTERFACE="$1"

# Run the command
sudo zerotier-cli -j -D"/config/vyos-generated-zerotier/$INTERFACE" bond list 2>/dev/null \
  | jq -r -e '.[] | select(.isBonded == true) | .address' 2>/dev/null
