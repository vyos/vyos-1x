#!/bin/bash

# Completion script used to select specific NTP server
/bin/cli-shell-api -- listEffectiveNodes system ntp server | sed "s/'//g"
