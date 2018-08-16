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
changes=0

if [ "$domain" == "..YYZ!" ]; then
    client_fqdn_name=$client_name
    client_search_expr=$client_name
else
    client_fqdn_name=$client_name.$domain
    client_search_expr="$client_name\\.$domain"
fi

case "$action" in
  commit) # add mapping for new lease
    echo "- new lease event, setting static mapping for host "\
         "$client_fqdn_name (MAC=$client_mac, IP=$client_ip)"
    #
    # grep fails miserably with \t in the search expression.
    # In the following line one <Ctrl-V> <TAB> is used after $client_search_expr
    # followed by a single space
    grep -q " $client_search_expr	 #on-dhcp-event " $file
    if [ $? == 0 ]; then
       echo pattern found, removing
       wc1=`cat $file | wc -l`
       sudo sed -i "/ $client_search_expr\t #on-dhcp-event /d" $file
       wc2=`cat $file | wc -l`
       if [ "$wc1" -eq "$wc2" ]; then
         echo No change
       fi
    else
       echo pattern NOT found
    fi

    # check if hostname already exists (e.g. a static host mapping)
    # if so don't overwrite
    grep -q " $client_search_expr	 " $file
    if [ $? == 0 ]; then
       echo host $client_fqdn_name already exists, exiting
       exit 1
    fi

    line="$client_ip\t $client_fqdn_name\t #on-dhcp-event $client_mac"
    sudo sh -c "echo -e '$line' >> $file"
    ((changes++))
    echo Entry was added
    ;;

  release) # delete mapping for released address
    echo "- lease release event, deleting static mapping for host $client_fqdn_name"
    wc1=`cat $file | wc -l`
    sudo sed -i "/ $client_search_expr\t #on-dhcp-event /d" $file
    wc2=`cat $file | wc -l`
    if [ "$wc1" -eq "$wc2" ]; then
      echo No change
    else
      echo Entry was removed
      ((changes++))
    fi
    ;;

  *)
    logger -s -t on-dhcp-event "Invalid command \"$1\""
    exit 1;
    ;;
esac

if [ $changes -gt 0 ]; then
  echo Success
  pid=`pgrep pdns_recursor`
  if [ -n "$pid" ]; then
     sudo rec_control reload-zones
  fi
else
  echo No changes made
fi
exit 0


