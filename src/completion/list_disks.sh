#!/bin/bash

# Completion script used by show disks to collect physical disk

awk 'NR > 2 && $4 !~ /[0-9]$/ { print $4 }' </proc/partitions
