(conntrack-sync)=

# Conntrack Sync

One of the important features built on top of the Netfilter framework is
connection tracking. Connection tracking allows the kernel to keep track of all
logical network connections or sessions, and thereby relate all of the packets
which may make up that connection. NAT relies on this information to translate
all related packets in the same way, and iptables can use this information to
act as a stateful firewall.

The connection state however is completely independent of any upper-level
state, such as TCP's or SCTP's state. Part of the reason for this is that when
merely forwarding packets, i.e. no local delivery, the TCP engine may not
necessarily be invoked at all. Even connectionless-mode transmissions such as
UDP, IPsec (AH/ESP), GRE and other tunneling protocols have, at least, a pseudo
connection state. The heuristic for such protocols is often based upon a preset
timeout value for inactivity, after whose expiration a Netfilter connection is
dropped.

Each Netfilter connection is uniquely identified by a (layer-3 protocol, source
address, destination address, layer-4 protocol, layer-4 key) tuple. The layer-4
key depends on the transport protocol; for TCP/UDP it is the port numbers, for
tunnels it can be their tunnel ID, but otherwise is just zero, as if it were
not part of the tuple. To be able to inspect the TCP port in all cases, packets
will be mandatorily defragmented.

It is possible to use either Multicast or Unicast to sync conntrack traffic.
Most examples below show Multicast, but unicast can be specified by using the
"peer" keyword after the specified interface, as in the following example:

{cfgcmd}`set service conntrack-sync interface eth0 peer 192.168.0.250`

## Configuration

```{cfgcmd} set service conntrack-sync accept-protocol

Accept only certain protocols: You may want to replicate the state of flows
depending on their layer 4 protocol.

Protocols are: tcp, sctp, dccp, udp, icmp and ipv6-icmp.
```


```{cfgcmd} set service conntrack-sync event-listen-queue-size \<size\>

The daemon doubles the size of the netlink event socket buffer size if it
detects netlink event message dropping. This clause sets the maximum buffer
size growth that can be reached.

Queue size for listening to local conntrack events in MB.
```


```{cfgcmd} set service conntrack-sync expect-sync \<all|ftp|h323|nfs|sip|sqlnet\>

Protocol for which expect entries need to be synchronized.
```


```{cfgcmd} set service conntrack-sync failover-mechanism vrrp sync-group \<group\>

Failover mechanism to use for conntrack-sync.

Only VRRP is supported. Required option.
```


```{cfgcmd} set service conntrack-sync ignore-address \<x.x.x.x\>

IP addresses or networks for which local conntrack entries will not be synced
```


```{cfgcmd} set service conntrack-sync interface \<name\>

Interface to use for syncing conntrack entries.
```


```{cfgcmd} set service conntrack-sync interface \<name\> port \<port\>

Port number used by connection.
```


```{cfgcmd} set service conntrack-sync listen-address \<ipv4address\>

Local IPv4 addresses for service to listen on.
```


```{cfgcmd} set service conntrack-sync mcast-group \<x.x.x.x\>

Multicast group to use for syncing conntrack entries.

Defaults to 225.0.0.50.
```


```{cfgcmd} set service conntrack-sync interface \<name\> peer \<address\>

Peer to send unicast UDP conntrack sync entries to, if not using Multicast
configuration from above.
```


```{cfgcmd} set service conntrack-sync sync-queue-size \<size\>

Queue size for syncing conntrack entries in MB.
```


```{cfgcmd} set service conntrack-sync disable-external-cache

This disables the external cache and directly injects the flow-states into the
in-kernel Connection Tracking System of the backup firewall.
```


```{cfgcmd} set service conntrack-sync purge-timeout \<timeout\>

Timeout (in seconds) for purging synchronized entries on handover events.

On handover, ``conntrackd -t`` is invoked, which schedules a conntrack table
flush after ``<timeout>`` seconds to purge stale (“zombie”) entries and
reduce clashes when multiple handovers occur in a short period.
The default is 60 seconds.
```

:::{note}
In VRRP stateful firewall deployments, align VRRP timing with this
behavior: because synchronized conntrack state is purged after the purge
timeout, set **VRRP preempt-delay** to ≥ **purge-timeout** so mastership
can be restored before conntrack state is purged.
:::

```{cfgcmd} set service conntrack-sync disable-syslog

Disable connection logging via Syslog.
```


```{cfgcmd} set service conntrack-sync startup-resync

Order conntrackd to request a complete conntrack table resync against
the other node at startup.
```

## Operation

```{opcmd} show conntrack table \<ipv4|ipv6\>

Make sure conntrack is enabled by running and show connection tracking table.

:::{code-block} none
vyos@vyos:~$ show conntrack table ipv4
Id          Original src    Original dst    Original packets    Original bytes    Reply src     Reply dst       Reply packets    Reply bytes    Protocol    State        Timeout    Mark    Zone
----------  --------------  --------------  ------------------  ----------------  ------------  --------------  ---------------  -------------  ----------  -----------  ---------  ------  ------
282920088   10.0.2.2:41724  10.0.2.15:22    79                  8741              10.0.2.15:22  10.0.2.2:41724  52               8495           tcp         TIME_WAIT    3          0
102466872   192.168.50.1    192.168.50.4    31953               2684052           192.168.50.4  192.168.50.1    31953            2684052        icmp                     29         0       110
1445684978  10.0.2.2:37762  10.0.2.15:22    111                 9969              10.0.2.15:22  10.0.2.2:37762  86               13323          tcp         ESTABLISHED  431999     0
3302843234  10.0.2.2:37758  10.0.2.15:22    2612                3845685           10.0.2.15:22  10.0.2.2:37758  254              17447          tcp         TIME_WAIT    11         0
:::
:::{note}
If the table is empty and you have a warning message, it means
conntrack is not enabled. To enable conntrack, just create a NAT or a firewall
rule.
{cfgcmd}`set firewall global-options state-policy established action accept`
:::
```


```{opcmd} show conntrack table \<ipv4|ipv6\> vrf \<vrf-name\>

Show connection tracking table filtered by VRF name. Only entries originating
from the specified VRF are displayed.
```


```{opcmd} show conntrack-sync cache external

Show connection syncing external cache entries
```


```{opcmd} show conntrack-sync cache internal

Show connection syncing internal cache entries
```


```{opcmd} show conntrack-sync statistics

Retrieve current statistics of connection tracking subsystem.

:::{code-block} none
vyos@vyos:~$ show conntrack-sync statistics
Main Table Statistics:

cache internal:
current active connections:            19606
connections created:                 6298470    failed:            0
connections updated:                 3786793    failed:            0
connections destroyed:               6278864    failed:            0

cache external:
current active connections:            15771
connections created:                 1660193    failed:            0
connections updated:                   77204    failed:            0
connections destroyed:               1644422    failed:            0

traffic processed:
0 Bytes                         0 Pckts

multicast traffic (active device=eth0.5):
976826240 Bytes sent            212898000 Bytes recv
8302333 Pckts sent              2009929 Pckts recv
0 Error send                    0 Error recv

message tracking:
0 Malformed msgs                  263 Lost msgs
:::
```
```{opcmd} show conntrack-sync status

Retrieve current status of connection tracking subsystem.

:::{code-block} none
vyos@vyos:~$ show conntrack-sync status
sync-interface        : eth0.5
failover-mechanism    : vrrp [sync-group GEFOEKOM]
last state transition : no transition yet!
ExpectationSync       : disabled
:::
```

## Example

The next example is a simple configuration of conntrack-sync.

:::{figure} /_static/images/service_conntrack_sync-schema.webp
:alt: Conntrack Sync Example
:scale: 60 %
:::

Now configure conntrack-sync service on `router1` **and** `router2`

```none
set high-availability vrrp group internal virtual-address ... etc ...
set high-availability vrrp sync-group syncgrp member 'internal'
set service conntrack-sync accept-protocol 'tcp'
set service conntrack-sync accept-protocol 'udp'
set service conntrack-sync accept-protocol 'icmp'
set service conntrack-sync failover-mechanism vrrp sync-group 'syncgrp'
set service conntrack-sync interface 'eth0'
set service conntrack-sync mcast-group '225.0.0.50'
```

On the active router, you should have information in the internal-cache of
conntrack-sync. The same current active connections number should be shown in
the external-cache of the standby router

On active router run:

```none
$ show conntrack-sync statistics

Main Table Statistics:

cache internal:
current active connections:               10
connections created:                    8517    failed:            0
connections updated:                     127    failed:            0
connections destroyed:                  8507    failed:            0

cache external:
current active connections:                0
connections created:                       0    failed:            0
connections updated:                       0    failed:            0
connections destroyed:                     0    failed:            0

traffic processed:
                   0 Bytes                         0 Pckts

multicast traffic (active device=eth0):
              868780 Bytes sent               224136 Bytes recv
               20595 Pckts sent                14034 Pckts recv
                   0 Error send                    0 Error recv

message tracking:
                   0 Malformed msgs                    0 Lost msgs
```

On standby router run:

```none
$ show conntrack-sync statistics

Main Table Statistics:

cache internal:
current active connections:                0
connections created:                       0    failed:            0
connections updated:                       0    failed:            0
connections destroyed:                     0    failed:            0

cache external:
current active connections:               10
connections created:                     888    failed:            0
connections updated:                     134    failed:            0
connections destroyed:                   878    failed:            0

traffic processed:
                   0 Bytes                         0 Pckts

multicast traffic (active device=eth0):
              234184 Bytes sent               907504 Bytes recv
               14663 Pckts sent                21495 Pckts recv
                   0 Error send                    0 Error recv

message tracking:
                   0 Malformed msgs                    0 Lost msgs
```
