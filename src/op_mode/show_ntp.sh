#!/bin/sh

sourcestats=0
tracking=0

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --sourcestats) sourcestats=1 ;;
        --tracking) tracking=1 ;;
        *) echo "Unknown parameter passed: $1" ;;
    esac
    shift
done

if ! ps -C chronyd &>/dev/null; then
    echo NTP daemon disabled
    exit 1
fi

PID=$(pgrep chronyd | head -n1)
VRF_NAME=$(ip vrf identify ${PID})

if [ ! -z ${VRF_NAME} ]; then
    VRF_CMD="sudo ip vrf exec ${VRF_NAME}"
fi

if [ $sourcestats -eq 1 ]; then
    $VRF_CMD chronyc sourcestats -v
elif [ $tracking -eq 1 ]; then
    $VRF_CMD chronyc tracking -v
else
    echo "Unknown option"
fi

