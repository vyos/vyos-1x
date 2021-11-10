#!/bin/bash
ROOT_PART_DEV=$(findmnt /usr/lib/live/mount/persistence -o source -n)
ROOT_PART_NAME=$(echo "$ROOT_PART_DEV" | cut -d "/" -f 3)
ROOT_DEV_NAME=$(echo /sys/block/*/"${ROOT_PART_NAME}" | cut -d "/" -f 4)
ROOT_DEV="/dev/${ROOT_DEV_NAME}"
ROOT_PART_NUM=$(cat "/sys/block/${ROOT_DEV_NAME}/${ROOT_PART_NAME}/partition")
NEXT_PART_NUM=$((ROOT_PART_NUM + 1))
ROOT_DEV_SIZE=$(cat "/sys/block/${ROOT_DEV_NAME}/size")
ROOT_PART_SIZE=$(cat "/sys/block/${ROOT_DEV_NAME}/${ROOT_PART_NAME}/size")
ROOT_PART_START=$(cat "/sys/block/${ROOT_DEV_NAME}/${ROOT_PART_NAME}/start")
AVAILABLE_EXTENSION_SIZE=$((ROOT_DEV_SIZE - ROOT_PART_START - ROOT_PART_SIZE - 1))
TARGET_END=$((ROOT_DEV_SIZE - 1))

if [ -d "/sys/block/${ROOT_DEV_NAME}/${ROOT_DEV_NAME}${NEXT_PART_NUM}/" ]; then
    echo "The root partition is not the last"
    exit 0;
fi

if [ $AVAILABLE_EXTENSION_SIZE -lt 1 ]; then
    echo "There is no available space for root partition extension"
    exit 0;
fi

parted -m ${ROOT_DEV} ---pretend-input-tty "u s resizepart ${ROOT_PART_NUM} Yes ${TARGET_END}s"
resize2fs "$ROOT_PART_DEV"


