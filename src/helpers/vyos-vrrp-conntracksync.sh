#!/bin/sh
#
# (C) 2008 by Pablo Neira Ayuso <pablo@netfilter.org>
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.
#
# Description:
#
# This is the script for primary-backup setups for keepalived
# (http://www.keepalived.org). You may adapt it to make it work with other
# high-availability managers.
#
# Modified by : Mohit Mehta <mohit@vyatta.com>
# Slight modifications were made to this script for running with Vyatta
# The original script came from 0.9.14 debian conntrack-tools package

CONNTRACKD_BIN=/usr/sbin/conntrackd
CONNTRACKD_LOCK=/var/lock/conntrack.lock
CONNTRACKD_CONFIG=/run/conntrackd/conntrackd.conf
FACILITY=daemon
LEVEL=notice
TAG=conntrack-tools
LOGCMD="logger -t $TAG -p $FACILITY.$LEVEL"
VRRP_GRP="VRRP sync-group [$2]"
FAILOVER_STATE="/var/run/vyatta-conntrackd-failover-state"

$LOGCMD "vyos-vrrp-conntracksync invoked at `date`"

if ! systemctl is-active --quiet conntrackd.service; then
    echo "conntrackd service not running"
    exit 1
fi

if [ ! -e $FAILOVER_STATE ]; then
	mkdir -p /var/run
	touch $FAILOVER_STATE
fi

case "$1" in
  master)
  	echo MASTER at `date` > $FAILOVER_STATE
    $LOGCMD "`uname -n` transitioning to MASTER state for $VRRP_GRP"
    #
    # commit the external cache into the kernel table
    #
    $CONNTRACKD_BIN -C $CONNTRACKD_CONFIG -c
    if [ $? -eq 1 ]
    then
        $LOGCMD "ERROR: failed to invoke conntrackd -c"
    fi

    #
    # commit the expect entries to the kernel
    #
    $CONNTRACKD_BIN -C $CONNTRACKD_CONFIG -c exp
    if [ $? -eq 1 ]
    then
        $LOGCMD "ERROR: failed to invoke conntrackd -ce exp"
    fi

    #
    # flush the internal and the external caches
    #
    $CONNTRACKD_BIN -C $CONNTRACKD_CONFIG -f
    if [ $? -eq 1 ]
    then
        $LOGCMD "ERROR: failed to invoke conntrackd -f"
    fi

    #
    # resynchronize my internal cache to the kernel table
    #
    $CONNTRACKD_BIN -C $CONNTRACKD_CONFIG -R
    if [ $? -eq 1 ]
    then
        $LOGCMD "ERROR: failed to invoke conntrackd -R"
    fi

    #
    # send a bulk update to backups
    #
    $CONNTRACKD_BIN -C $CONNTRACKD_CONFIG -B
    if [ $? -eq 1 ]
    then
        $LOGCMD "ERROR: failed to invoke conntrackd -B"
    fi
    ;;
  backup)
  	echo BACKUP at `date` > $FAILOVER_STATE
    $LOGCMD "`uname -n` transitioning to BACKUP state for $VRRP_GRP"
    #
    # is conntrackd running? request some statistics to check it
    #
    $CONNTRACKD_BIN -C $CONNTRACKD_CONFIG -s
    if [ $? -eq 1 ]
    then
        #
        # something's wrong, do we have a lock file?
        #
        if [ -f $CONNTRACKD_LOCK ]
        then
            $LOGCMD "WARNING: conntrackd was not cleanly stopped."
            $LOGCMD "If you suspect that it has crashed:"
            $LOGCMD "1) Enable coredumps"
            $LOGCMD "2) Try to reproduce the problem"
            $LOGCMD "3) Post the coredump to netfilter-devel@vger.kernel.org"
            rm -f $CONNTRACKD_LOCK
        fi
        $CONNTRACKD_BIN -C $CONNTRACKD_CONFIG -d
        if [ $? -eq 1 ]
        then
            $LOGCMD "ERROR: cannot launch conntrackd"
            exit 1
        fi
    fi
    #
    # shorten kernel conntrack timers to remove the zombie entries.
    #
    $CONNTRACKD_BIN -C $CONNTRACKD_CONFIG -t
    if [ $? -eq 1 ]
    then
        $LOGCMD "ERROR: failed to invoke conntrackd -t"
    fi

    #
    # request resynchronization with master firewall replica (if any)
    # Note: this does nothing in the alarm approach.
    #
    $CONNTRACKD_BIN -C $CONNTRACKD_CONFIG -n
    if [ $? -eq 1 ]
    then
        $LOGCMD "ERROR: failed to invoke conntrackd -n"
    fi
    ;;
  fault)
  	echo FAULT at `date` > $FAILOVER_STATE
    $LOGCMD "`uname -n` transitioning to FAULT state for $VRRP_GRP"
    #
    # shorten kernel conntrack timers to remove the zombie entries.
    #
    $CONNTRACKD_BIN -C $CONNTRACKD_CONFIG -t
    if [ $? -eq 1 ]
    then
        $LOGCMD "ERROR: failed to invoke conntrackd -t"
    fi
    ;;
  *)
  	echo UNKNOWN at `date` > $FAILOVER_STATE
    $LOGCMD "ERROR: `uname -n` unknown state transition for $VRRP_GRP"
    echo "Usage: vyos-vrrp-conntracksync.sh {master|backup|fault}"
    exit 1
    ;;
esac

exit 0
