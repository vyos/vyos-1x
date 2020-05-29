#!/bin/sh

if cli-shell-api existsEffective service dns dynamic; then
    echo "Restarting dynamic DNS service"
    systemctl restart ddclient.service
else
    echo "Dynamic DNS update service is not configured"
fi
