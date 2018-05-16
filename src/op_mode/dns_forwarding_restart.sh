#!/bin/sh

if cli-shell-api exists service dns forwarding; then
    echo "Restarting the DNS forwarding service"
    systemctl restart pdns-recursor
else
    echo "DNS forwarding is not configured"
fi
