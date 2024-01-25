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
    lease_addr=$LEASE6_ADDRESS
    lease_prefix_len=$LEASE6_PREFIX_LEN

    if [[ "$LEASE6_TYPE" != "IA_PD" ]]; then
      exit 0
    fi

    logger -s -t on-dhcpv6-event "Processing route deletion for ${lease_addr}/${lease_prefix_len}"
    route_cmd="sudo -n /sbin/ip -6 route del ${lease_addr}/${lease_prefix_len}"

    # the ifname is not always present, like in LEASE6_VALID_LIFETIME=0 updates,
    # but 'route del' works either way. Use interface only if there is one.
    if [[ "$ifname" != "" ]]; then
        route_cmd+=" dev ${ifname}"
    fi
    route_cmd+=" proto static"
    eval "$route_cmd"

    exit 0
    ;;

  leases6_committed)
    for ((i = 0; i < $LEASES6_SIZE; i++)); do
      ifname=$QUERY6_IFACE_NAME
      requester_link_local=$QUERY6_REMOTE_ADDR
      lease_type_var="LEASES6_AT${i}_TYPE"
      lease_ip_var="LEASES6_AT${i}_ADDRESS"
      lease_prefix_len_var="LEASES6_AT${i}_PREFIX_LEN"

      lease_type=${!lease_type_var}

      if [[ "$lease_type" != "IA_PD" ]]; then
        continue
      fi

      lease_ip=${!lease_ip_var}
      lease_prefix_len=${!lease_prefix_len_var}

      logger -s -t on-dhcpv6-event "Processing PD route for ${lease_addr}/${lease_prefix_len}. Link local: ${requester_link_local} ifname: ${ifname}"
      
      sudo -n /sbin/ip -6 route replace ${lease_ip}/${lease_prefix_len} \
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
