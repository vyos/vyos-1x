#!/bin/sh
DB_DIR="/config/url-filtering/squidguard/db/"
if [ -d ${DB_DIR} ]; then
    ls -ald ${DB_DIR}/* | grep -E '^(d|l)' | awk '{print $9}' | sed s#${DB_DIR}/##
fi
