#!/bin/sh
source /opt/vyatta/etc/functions/script-template
/usr/libexec/vyos/conf_mode/pki.py certbot_renew
