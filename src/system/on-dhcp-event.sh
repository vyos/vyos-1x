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
hostsd_client="/usr/bin/vyos-hostsd-client"

case "$action" in
  commit) # add mapping for new lease
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
    $hostsd_client --add-hosts "$client_fqdn_name,$client_ip" --tag "dhcp-server-$client_ip" --apply
    exit 0
    ;;

  release) # delete mapping for released address
    $hostsd_client --delete-hosts --tag "dhcp-server-$client_ip" --apply
    exit 0
    ;;

<<<<<<< HEAD
=======
  leases4_committed) # process committed leases (added/renewed/recovered)
    for ((i = 0; i < $LEASES4_SIZE; i++)); do
      client_ip_var="LEASES4_AT${i}_ADDRESS"
      client_mac_var="LEASES4_AT${i}_HWADDR"
      client_name_var="LEASES4_AT${i}_HOSTNAME"
      client_subnet_id_var="LEASES4_AT${i}_SUBNET_ID"

      client_ip=${!client_ip_var}
      client_mac=${!client_mac_var}
      client_name=${!client_name_var//./}
      client_subnet_id=${!client_subnet_id_var}

      if [ -z "$client_name" ]; then
          logger -s -t on-dhcp-event "Client name was empty, using MAC \"$client_mac\" instead"
          client_name=$(echo "host-$client_mac" | tr : -)
      fi

      client_domain=$(get_subnet_domain_name $client_subnet_id)

      if [ -n "$client_domain" ]; then
        client_name="$client_name.$client_domain"
      fi

      $hostsd_client --add-hosts "$client_name,$client_ip" --tag "dhcp-server-$client_ip" --apply
    done

    exit 0
    ;;

>>>>>>> 2da78b428 (dhcp: T5948: Strip trailing dot from hostnames)
  *)
    logger -s -t on-dhcp-event "Invalid command \"$1\""
    exit 1
    ;;
esac

exit 0
