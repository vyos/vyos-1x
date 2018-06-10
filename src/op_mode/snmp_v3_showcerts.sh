#!/bin/sh

files=`sudo ls /etc/snmp/tls/certs/ 2> /dev/null`;
if [ -n "$files" ]; then
  sudo /usr/bin/net-snmp-cert showcerts --subject --fingerprint
else
  echo "You don't have any certificates. Put it in '/etc/snmp/tls/certs/' folder."
fi
