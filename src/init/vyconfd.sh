#!/bin/bash
#
# Check if state file exists to determine if restart
if [ -f /var/run/vyconfd.state ]; then
    echo "Restarting vyconfd from active config"
    /usr/libexec/vyos/vyconf/vyconfd --log-file /var/run/log/vyconfd.log --reload-active-config --legacy-config-path
else
    echo "Starting vyconfd from saved config"
    touch /var/run/vyconfd.state
    /usr/libexec/vyos/vyconf/vyconfd --log-file /var/run/log/vyconfd.log --legacy-config-path
fi
