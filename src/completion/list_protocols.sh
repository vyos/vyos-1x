#!/bin/sh

grep -v '^#' /etc/protocols | awk 'BEGIN {ORS=""} {if ($3) {print TRS $1; TRS=" "}}'
