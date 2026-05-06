################
Route Map Policy
################

Route map is a powerfull command, that gives network administrators a very
useful and flexible tool for traffic manipulation.

*************
Configuration
*************

Route Map
=========

.. cfgcmd:: set policy route-map <text>

   This command creates a new route-map policy, identified by <text>.

.. cfgcmd:: set policy route-map <text> description <text>

   Set description for the route-map policy.

.. cfgcmd:: set policy route-map <text> rule <1-65535> action <permit|deny>

   Set action for the route-map policy.

.. cfgcmd:: set policy route-map <text> rule <1-65535> call <text>

   Call another route-map policy on match.

.. cfgcmd:: set policy route-map <text> rule <1-65535> continue <1-65535>

   Jump to a different rule in this route-map on a match.

.. cfgcmd:: set policy route-map <text> rule <1-65535> description <text>

   Set description for the rule in the route-map policy.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match as-path <text>

   BGP as-path list to match.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match community
   community-list <text>

   BGP community-list to match.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match community
   exact-match

   Set BGP community-list to exactly match.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match extcommunity
   <text>

   BGP extended community to match.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match interface <text>

   First hop interface of a route to match.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match ip address
   access-list <1-2699>

   IP address of route to match, based on access-list.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match ip address
   prefix-list <text>

   IP address of route to match, based on prefix-list.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match ip address
   prefix-len <0-32>

   IP address of route to match, based on specified prefix-length.
   Note that this can be used for kernel routes only.
   Do not apply to the routes of dynamic routing protocols (e.g. BGP,
   RIP, OSFP), as this can lead to unexpected results..

.. cfgcmd:: set policy route-map <text> rule <1-65535> match ip nexthop
   access-list <1-2699>

   IP next-hop of route to match, based on access-list.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match ip nexthop
   address <x.x.x.x>

   IP next-hop of route to match, based on ip address.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match ip nexthop
   prefix-len <0-32>

   IP next-hop of route to match, based on prefix length.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match ip nexthop
   prefix-list <text>

   IP next-hop of route to match, based on prefix-list.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match ip nexthop
   type <blackhole>

   IP next-hop of route to match, based on type.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match ip route-source
   access-list <1-2699>

   IP route source of route to match, based on access-list.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match ip route-source
   prefix-list <text>

   IP route source of route to match, based on prefix-list.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match ipv6 address
   access-list <text>

   IPv6 address of route to match, based on IPv6 access-list.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match ipv6 address
   prefix-list <text>

   IPv6 address of route to match, based on IPv6 prefix-list.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match ipv6 address
   prefix-len <0-128>

   IPv6 address of route to match, based on specified prefix-length.
   Note that this can be used for kernel routes only.
   Do not apply to the routes of dynamic routing protocols (e.g. BGP,
   RIP, OSFP), as this can lead to unexpected results..

.. cfgcmd:: set policy route-map <text> rule <1-65535> match ipv6 nexthop
   <h:h:h:h:h:h:h:h>

   Nexthop IPv6 address to match.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match large-community
   large-community-list <text>

   Match BGP large communities.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match local-preference
   <0-4294967295>

   Match local preference.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match metric <1-65535>

   Match route metric.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match origin
   <egp|igp|incomplete>

   Boarder Gateway Protocol (BGP) origin code to match.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match peer <x.x.x.x>

   Peer IP address to match.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match protocol <protocol>

   Source protocol to match.
     * ``babel`` - Babel routing protocol (Babel)
     * ``bgp`` - Border Gateway Protocol (BGP)
     * ``connected`` - Connected routes (directly attached subnet or host)
     * ``isis`` - Intermediate System to Intermediate System (IS-IS)
     * ``kernel`` - Kernel routes
     * ``ospf`` - Open Shortest Path First (OSPFv2)
     * ``ospfv3`` - Open Shortest Path First (IPv6) (OSPFv3)
     * ``rip`` - Routing Information Protocol (RIP)
     * ``ripng`` - Routing Information Protocol next-generation (IPv6) (RIPng)
     * ``static`` - Statically configured routes
     * ``table`` - Non-main Kernel Routing Table
     * ``vnc`` - Virtual Network Control (VNC)

.. cfgcmd:: set policy route-map <text> rule <1-65535> match rpki
   <invalid|notfound|valid>

   Match RPKI validation result.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match source-vrf <text>

   Source VRF to match.

.. cfgcmd:: set policy route-map <text> rule <1-65535> match tag <1-65535>

   Route tag to match.

.. cfgcmd:: set policy route-map <text> rule <1-65535> on-match goto <1-65535>

   Exit policy on match: go to rule <1-65535>

.. cfgcmd:: set policy route-map <text> rule <1-65535> on-match next

   Exit policy on match: go to next sequence number.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set aggregator <as|ip>
   <1-4294967295|x.x.x.x>

   BGP aggregator attribute: AS number or IP address of an aggregation.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set as-path exclude
   <1-4294967295 | all>

   Drop AS-NUMBER from the BGP AS path.

   If ``all`` is specified, remove all AS numbers from the AS_PATH of the BGP
   path's NLRI.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set as-path prepend
   <1-4294967295>

   Prepend the given string of AS numbers to the AS_PATH of the BGP path's NLRI.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set as-path
   prepend-last-as <n>

   Prepend the existing last AS number (the leftmost ASN) to the AS_PATH.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set atomic-aggregate

   BGP atomic aggregate attribute.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set community
   <add|replace> <community>

   Add or replace BGP community attribute in format ``<0-65535:0-65535>``
   or from well-known community list

.. cfgcmd:: set policy route-map <text> rule <1-65535> set community none

   Delete all BGP communities

.. cfgcmd:: set policy route-map <text> rule <1-65535> set community delete
   <text>

   Delete BGP communities matching the community-list.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set large-community
   <add|replace> <GA:LDP1:LDP2>

   Add or replace BGP large-community attribute in format
   ``<0-4294967295:0-4294967295:0-4294967295>``

.. cfgcmd:: set policy route-map <text> rule <1-65535> set large-community none

   Delete all BGP large-communities

.. cfgcmd:: set policy route-map <text> rule <1-65535> set large-community delete
   <text>

   Delete BGP communities matching the large-community-list.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set extcommunity bandwidth
   <1-25600|cumulative|num-multipaths>

   Set extcommunity bandwidth

.. cfgcmd:: set policy route-map <text> rule <1-65535> set extcommunity bandwidth-non-transitive

   The link bandwidth extended community is encoded as non-transitive

.. cfgcmd:: set policy route-map <text> rule <1-65535> set extcommunity rt
   <text>

   Set route target value in format ``<0-65535:0-4294967295>`` or ``<IP:0-65535>``.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set extcommunity soo
   <text>

   Set site of origin value in format ``<0-65535:0-4294967295>`` or ``<IP:0-65535>``.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set extcommunity none

   Clear all BGP extcommunities.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set distance <0-255>

   Locally significant administrative distance.


.. cfgcmd:: set policy route-map <text> rule <1-65535> set ip-next-hop
   <x.x.x.x>

   Nexthop IP address.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set ip-next-hop
   unchanged

   Set the next-hop as unchanged. Pass through the route-map without
   changing its value

.. cfgcmd:: set policy route-map <text> rule <1-65535> set ip-next-hop
   peer-address

   Set the BGP nexthop address to the address of the peer. For an incoming
   route-map this means the ip address of our peer is used. For an
   outgoing route-map this means the ip address of our self is used to
   establish the peering with our neighbor.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set ipv6-next-hop
   <global|local> <h:h:h:h:h:h:h:h>

   Nexthop IPv6 address.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set ipv6-next-hop
   peer-address

   Set the BGP nexthop address to the address of the peer. For an incoming
   route-map this means the ip address of our peer is used. For an
   outgoing route-map this means the ip address of our self is used to
   establish the peering with our neighbor.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set ipv6-next-hop
   prefer-global

   For Incoming and Import Route-maps if we receive a v6 global and v6 LL
   address for the route, then prefer to use the global address as the
   nexthop.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set local-preference
   <0-4294967295>

   Set BGP local preference attribute.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set metric
   <+/-metric|0-4294967295|rtt|+rtt|-rtt>

   Set the route metric. When used with BGP, set the BGP attribute MED
   to a specific value. Use ``+/-`` to add or subtract the specified value
   to/from the existing/MED. Use ``rtt`` to set the MED to the round trip
   time or ``+rtt/-rtt`` to add/subtract the round trip time to/from the MED.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set metric-type
   <type-1|type-2>

   Set OSPF external metric-type.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set origin
   <igp|egp|incomplete>

   Set BGP origin code.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set originator-id
   <x.x.x.x>

   Set BGP originator ID attribute.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set src
   <x.x.x.x|h:h:h:h:h:h:h:h>

   Set source IP/IPv6 address for route.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set table <1-200>

   Set prefixes to table.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set tag <1-65535>

   Set tag value for routing protocol.

.. cfgcmd:: set policy route-map <text> rule <1-65535> set weight
   <0-4294967295>

   Set BGP weight attribute

List of well-known communities
==============================
   * ``local-as`` -                     Well-known communities value NO_EXPORT_SUBCONFED 0xFFFFFF03
   * ``no-advertise`` -                 Well-known communities value NO_ADVERTISE 0xFFFFFF02
   * ``no-export`` -                    Well-known communities value NO_EXPORT 0xFFFFFF01
   * ``graceful-shutdown`` -            Well-known communities value GRACEFUL_SHUTDOWN 0xFFFF0000
   * ``accept-own`` -                   Well-known communities value ACCEPT_OWN 0xFFFF0001
   * ``route-filter-translated-v4`` -   Well-known communities value ROUTE_FILTER_TRANSLATED_v4 0xFFFF0002
   * ``route-filter-v4`` -              Well-known communities value ROUTE_FILTER_v4 0xFFFF0003
   * ``route-filter-translated-v6`` -   Well-known communities value ROUTE_FILTER_TRANSLATED_v6 0xFFFF0004
   * ``route-filter-v6`` -              Well-known communities value ROUTE_FILTER_v6 0xFFFF0005
   * ``llgr-stale`` -                   Well-known communities value LLGR_STALE 0xFFFF0006
   * ``no-llgr`` -                      Well-known communities value NO_LLGR 0xFFFF0007
   * ``accept-own-nexthop`` -           Well-known communities value accept-own-nexthop 0xFFFF0008
   * ``blackhole`` -                    Well-known communities value BLACKHOLE 0xFFFF029A
   * ``no-peer`` -                      Well-known communities value NOPEER 0xFFFFFF04
