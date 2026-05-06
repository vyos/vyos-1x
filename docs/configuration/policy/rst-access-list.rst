##################
Access List Policy
##################

Filtering is used for both input and output of the routing information. Once
filtering is defined, it can be applied in any direction. VyOS makes filtering
possible using acls and prefix lists.

Basic filtering can be done using access-list and access-list6.

*************
Configuration
*************

Access Lists
============

.. cfgcmd:: set policy access-list <acl_number>

   This command creates the new access list policy, where <acl_number> must be
   a number from 1 to 2699.

.. cfgcmd:: set policy access-list <acl_number> description <text>

   Set description for the access list.

.. cfgcmd:: set policy access-list <acl_number> rule <1-65535> action
   <permit|deny>

   This command creates a new rule in the access list and defines an action.

.. cfgcmd:: set policy access-list <acl_number> rule <1-65535>
   <destination|source> <any|host|inverse-mask|network>

   This command defines matching parameters for access list rule. Matching
   criteria could be applied to destination or source parameters:

   * any: any IP address to match.
   * host: single host IP address to match.
   * inverse-match: network/netmask to match (requires network be defined).
   * network: network/netmask to match (requires inverse-match be defined).

IPv6 Access List
================

Basic filtering could also be applied to IPv6 traffic.

.. cfgcmd:: set policy access-list6 <text>

   This command creates the new IPv6 access list, identified by <text>

.. cfgcmd:: set policy access-list6 <text> description <text>

   Set description for the IPv6 access list.

.. cfgcmd:: set policy access-list6 <text> rule <1-65535> action <permit|deny>

   This command creates a new rule in the IPv6 access list and defines an
   action.

.. cfgcmd:: set policy access-list6 <text> rule <1-65535> source
   <any|exact-match|network>

   This command defines matching parameters for IPv6 access list rule. Matching
   criteria could be applied to source parameters:

   * any: any IPv6 address to match.
   * exact-match: exact match of the network prefixes.
   * network: network/netmask to match (requires inverse-match be defined) BUG,
     NO invert-match option in access-list6