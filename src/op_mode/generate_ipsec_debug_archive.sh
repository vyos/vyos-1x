#!/usr/bin/env bash

# Collecting IPSec Debug Information

DATE=`date +%d-%m-%Y`

a_CMD=(
       "sudo ipsec status"
       "sudo swanctl -L"
       "sudo swanctl -l"
       "sudo swanctl -P"
       "sudo ip x sa show"
       "sudo ip x policy show"
       "sudo ip tunnel show"
       "sudo ip address"
       "sudo ip rule show"
       "sudo ip route"
       "sudo ip route show table 220"
      )


echo "DEBUG: ${DATE} on host \"$(hostname)\"" > /tmp/ipsec-status-${DATE}.txt
date >> /tmp/ipsec-status-${DATE}.txt

# Execute all DEBUG commands and save it to file
for cmd in "${a_CMD[@]}"; do
    echo -e "\n### ${cmd} ###" >> /tmp/ipsec-status-${DATE}.txt
    ${cmd} >> /tmp/ipsec-status-${DATE}.txt 2>/dev/null
done

# Collect charon logs, build .tgz archive
sudo journalctl /usr/lib/ipsec/charon > /tmp/journalctl-charon-${DATE}.txt && \
sudo tar -zcvf /tmp/ipsec-debug-${DATE}.tgz /tmp/journalctl-charon-${DATE}.txt /tmp/ipsec-status-${DATE}.txt >& /dev/null
sudo rm -f /tmp/journalctl-charon-${DATE}.txt /tmp/ipsec-status-${DATE}.txt

echo "Debug file is generated and located in /tmp/ipsec-debug-${DATE}.tgz"
