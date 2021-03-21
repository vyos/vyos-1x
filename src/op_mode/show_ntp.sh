#!/bin/sh

basic=0
info=0

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --info) info=1 ;;
        --basic) basic=1 ;;
        --server) server=$2; shift ;;
        *) echo "Unknown parameter passed: $1" ;;
    esac
    shift
done

if ! ps -C ntpd &>/dev/null; then
    echo NTP daemon disabled
    exit 1
fi

PID=$(pgrep ntpd)
VRF_NAME=$(ip vrf identify ${PID})

if [ ! -z ${VRF_NAME} ]; then
    VRF_CMD="sudo ip vrf exec ${VRF_NAME}"
fi

if [ $basic -eq 1 ]; then
    $VRF_CMD ntpq -n -c peers
elif [ $info -eq 1 ]; then
    echo "=== sysingo ==="
    $VRF_CMD ntpq -n -c sysinfo
    echo
    echo "=== kerninfo ==="
    $VRF_CMD ntpq -n -c kerninfo
elif [ ! -z $server ]; then
    $VRF_CMD /usr/sbin/ntpdate -q $server
fi

