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
client_name=$2
client_ip=$3
client_mac=$4
domain=$5
file=/etc/hosts

if [ -z "$client_name" ]; then
    logger -s -t on-dhcp-event "Client name was empty, using MAC \"$client_mac\" instead"
    client_name=$(echo "client-"$client_mac | tr : -)
fi

if [ "$domain" == "..YYZ!" ]; then
    client_fqdn_name=$client_name
    client_search_expr=$client_name
else
    client_fqdn_name=$client_name.$domain
    client_search_expr="$client_name\\.$domain"
fi

case "$action" in
  commit) # add mapping for new lease
    grep -q "   $client_search_expr     " $file
    if [ $? == 0 ]; then
       echo host $client_fqdn_name already exists, exiting
       exit 1
    fi
    # add host
    /usr/bin/vyos-hostsd-client --add-hosts --tag "DHCP-$client_ip" --host "$client_fqdn_name,$client_ip"
    ;;

  release) # delete mapping for released address
    # delete host
    /usr/bin/vyos-hostsd-client --delete-hosts --tag "DHCP-$client_ip"
    ;;

  *)
    logger -s -t on-dhcp-event "Invalid command \"$1\""
    exit 1;
    ;;
esac

exit 0


