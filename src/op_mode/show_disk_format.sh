#!/bin/bash

disk_dev="/dev/$1"
if [ ! -b "$disk_dev" ];then 
  echo "$3 is not a disk device"
  exit 1
fi
sudo /sbin/fdisk -l "$disk_dev"
