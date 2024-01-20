#!/bin/bash
#
# Copyright (C) 2024 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#

if [ $# -lt 1 ]; then
  echo Invalid args
  logger -s -t on-dhcpv6-event "Invalid args \"$@\""
  exit 1
fi

action=$1

case "$action" in
  lease6_renew|lease6_recover)
    exit 0
    ;;

  lease6_release|lease6_expire|lease6_decline)
    ifname=$QUERY6_IFACE_NAME
    client_ip=$LEASE6_ADDRESS
    client_prefix_len=$LEASE6_PREFIX_LEN

    if [[ "$LEASE6_TYPE" != "IA_PD" ]]; then
      exit 0
    fi

    sudo -n /sbin/ip -6 route del ${client_ip}/${client_prefix_len} \
      dev ${ifname} \
      proto static

    exit 0
    ;;

  leases6_committed)
    for ((i = 0; i < $LEASES6_SIZE; i++)); do
      ifname=$QUERY6_IFACE_NAME
      requester_link_local=$QUERY6_REMOTE_ADDR
      client_type_var="LEASES6_AT${i}_TYPE"
      client_ip_var="LEASES6_AT${i}_ADDRESS"
      client_prefix_len_var="LEASES6_AT${i}_PREFIX_LEN"

      client_type=${!client_type_var}

      if [[ "$client_type" != "IA_PD" ]]; then
        continue
      fi

      client_ip=${!client_ip_var}
      client_prefix_len=${!client_prefix_len_var}
      
      sudo -n /sbin/ip -6 route replace ${client_ip}/${client_prefix_len} \
        via ${requester_link_local} \
        dev ${ifname} \
        proto static
    done

    exit 0
    ;;

  *)
    logger -s -t on-dhcpv6-event "Invalid command \"$1\""
    exit 1
    ;;
esac
