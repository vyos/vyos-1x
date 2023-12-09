#!/bin/bash

# This script came from ubnt.com forum user "bradd" in the following post
# http://community.ubnt.com/t5/EdgeMAX/Automatic-DNS-resolution-of-DHCP-client-names/td-p/651311
# It has been modified by Ubiquiti to update the /etc/host file
# instead of adding to the CLI.
# Thanks to forum user "itsmarcos" for bug fix & improvements
# Thanks to forum user "ruudboon" for multiple domain fix
# Thanks to forum user "chibby85" for expire patch and static-mapping

if [ $# -lt 5 ]; then
  echo Invalid args
  logger -s -t on-dhcp-event "Invalid args \"$@\""
  exit 1
fi

action=$1
client_name=$LEASE4_HOSTNAME
client_ip=$LEASE4_ADDRESS
client_mac=$LEASE4_HWADDR
domain=$(echo "$client_name" | cut -d"." -f2-)
hostsd_client="/usr/bin/vyos-hostsd-client"

case "$action" in
  leases4_renew|lease4_recover) # add mapping for new lease
    if [ -z "$client_name" ]; then
        logger -s -t on-dhcp-event "Client name was empty, using MAC \"$client_mac\" instead"
        client_name=$(echo "client-"$client_mac | tr : -)
    fi

    if [ -z "$domain" ]; then
        client_fqdn_name=$client_name
        client_search_expr=$client_name
    else
        client_fqdn_name=$client_name.$domain
        client_search_expr="$client_name\\.$domain"
    fi
    $hostsd_client --add-hosts "$client_fqdn_name,$client_ip" --tag "dhcp-server-$client_ip" --apply
    exit 0
    ;;

  lease4_release|lease4_expire) # delete mapping for released address)
    $hostsd_client --delete-hosts --tag "dhcp-server-$client_ip" --apply
    exit 0
    ;;

  *)
    logger -s -t on-dhcp-event "Invalid command \"$1\""
    exit 1
    ;;
esac

exit 0
