#!/bin/bash

echo -n `cat /proc/partitions | grep md | awk '{ print $4 }'`
