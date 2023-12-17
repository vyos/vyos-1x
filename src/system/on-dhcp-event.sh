#!/bin/bash

# This script came from ubnt.com forum user "bradd" in the following post
# http://community.ubnt.com/t5/EdgeMAX/Automatic-DNS-resolution-of-DHCP-client-names/td-p/651311
# It has been modified by Ubiquiti to update the /etc/host file
# instead of adding to the CLI.
# Thanks to forum user "itsmarcos" for bug fix & improvements
# Thanks to forum user "ruudboon" for multiple domain fix
# Thanks to forum user "chibby85" for expire patch and static-mapping

if [ $# -lt 1 ]; then
  echo Invalid args
  logger -s -t on-dhcp-event "Invalid args \"$@\""
  exit 1
fi

action=$1
client_name=$LEASE4_HOSTNAME
client_ip=$LEASE4_ADDRESS
client_mac=$LEASE4_HWADDR
hostsd_client="/usr/bin/vyos-hostsd-client"

case "$action" in
  lease4_renew|lease4_recover) # add mapping for new/recovered lease address
    if [ -z "$client_name" ]; then
        logger -s -t on-dhcp-event "Client name was empty, using MAC \"$client_mac\" instead"
        client_name=$(echo "host-$client_mac" | tr : -)
    fi

    $hostsd_client --add-hosts "$client_name,$client_ip" --tag "dhcp-server-$client_ip" --apply
    exit 0
    ;;

  lease4_release|lease4_expire|lease4_decline) # delete mapping for released/declined address
    $hostsd_client --delete-hosts --tag "dhcp-server-$client_ip" --apply
    exit 0
    ;;

  leases4_committed) # nothing to do
    exit 0
    ;;

  *)
    logger -s -t on-dhcp-event "Invalid command \"$1\""
    exit 1
    ;;
esac
