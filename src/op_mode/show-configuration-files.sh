#!/bin/bash

# Wrapper script for the show configuration files command
find ${vyatta_sysconfdir}/config/ \
    -type f \
    -not -name ".*" \
    -not -name "config.boot.*" \
    -printf "%f\t(%Tc)\t%T@\n" \
        | sort -r -k3 \
        | awk -F"\t" '{printf ("%-20s\t%s\n", $1,$2) ;}'
