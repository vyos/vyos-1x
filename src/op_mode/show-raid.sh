#!/bin/bash

raid_set_name=$1
raid_sets=`cat /proc/partitions | grep md | awk '{ print $4 }'`
valid_set=`echo $raid_sets | grep $raid_set_name`
if [ -z $valid_set ]; then
    echo "$raid_set_name is not a RAID set"
else
    if [ -r /dev/${raid_set_name} ]; then
        # This should work without sudo because we have read
        # access to the dev, but for some reason mdadm must be
        # run as root in order to succeed.
        sudo /sbin/mdadm --detail /dev/${raid_set_name}
    else
        echo "Must be administrator or root to display RAID status"
    fi
fi
