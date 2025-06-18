#!/bin/sh

if test -f /run/suricata/suricata.yaml; then
  suricata-update --suricata-conf /run/suricata/suricata.yaml;
  systemctl restart suricata;
else
  echo "Service Suricata not configured";
fi
