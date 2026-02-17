#!/bin/bash

first_tty="$1"
second_tty="$2"

first_ttynum="${first_tty//[!0-9]/}"

if [ -n "$second_tty" ]; then
    second_ttynum="${second_tty//[!0-9]/}"
    iol_serialt "$first_ttynum" "$second_ttynum" -show
else
    iol_serialt "$first_ttynum" -show
fi
