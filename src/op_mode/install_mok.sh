#!/bin/sh

if test -f /var/lib/shim-signed/mok/vyos-dev-2025-shim.der; then
    mokutil --ignore-keyring --import /var/lib/shim-signed/mok/vyos-dev-2025-shim.der;
else
    echo "Secure Boot Machine Owner Key not found";
fi
