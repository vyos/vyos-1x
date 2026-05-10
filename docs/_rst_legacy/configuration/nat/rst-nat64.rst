.. _nat64:

#####
NAT64
#####

:abbr:`NAT64 (IPv6-to-IPv4 Prefix Translation)` is a critical component in
modern networking, facilitating communication between IPv6 and IPv4 networks.
This documentation outlines the setup, configuration, and usage of the NAT64
feature in your project. Whether you are transitioning to IPv6 or need to
seamlessly connect IPv4 and IPv6 devices.
NAT64 is a stateful translation mechanism that translates IPv6 addresses to
IPv4 addresses and IPv4 addresses to IPv6 addresses. NAT64 is used to enable
IPv6-only clients to contact IPv4 servers using unicast UDP, TCP, or ICMP.


Overview
========

Different NAT Types
-------------------

.. _source-nat64:

SNAT64
^^^^^^

:abbr:`SNAT64 (IPv6-to-IPv4 Source Address Translation)` is a stateful
translation mechanism that translates IPv6 addresses to IPv4 addresses.

``64:ff9b::/96`` is the well-known prefix for IPv4-embedded IPv6 addresses.
The prefix is used to represent IPv4 addresses in an IPv6 address format.
The IPv4 address is encoded in the low-order 32 bits of the IPv6 address.
The high-order 32 bits are set to the well-known prefix 64:ff9b::/96.


Configuration Examples
======================

The following examples show how to configure NAT64 on a VyOS router.
The 192.0.2.10 address is used as the IPv4 address for the translation pool.


NAT64 server configuration:

.. code-block:: none

  set interfaces ethernet eth0 address '192.0.2.1/24'
  set interfaces ethernet eth0 address '192.0.2.10/24'
  set interfaces ethernet eth0 description 'WAN'
  set interfaces ethernet eth1 address '2001:db8::1/64'
  set interfaces ethernet eth1 description 'LAN'

  set service dns forwarding allow-from '2001:db8::/64'
  set service dns forwarding dns64-prefix '64:ff9b::/96'
  set service dns forwarding listen-address '2001:db8::1'

  set nat64 source rule 100 source prefix '64:ff9b::/96'
  set nat64 source rule 100 translation pool 10 address '192.0.2.10'
  set nat64 source rule 100 translation pool 10 port '1-65535'

NAT64 client configuration:

.. code-block:: none

  set interfaces ethernet eth1 address '2001:db8::2/64'
  set protocols static route6 64:ff9b::/96 next-hop 2001:db8::1
  set system name-server '2001:db8::1'

Test from the IPv6 only client:

.. stop_vyoslinter

.. code-block:: none

  vyos@r1:~$ ping 64:ff9b::192.0.2.1 count 2
  PING 64:ff9b::192.0.2.1(64:ff9b::c000:201) 56 data bytes
  64 bytes from 64:ff9b::c000:201: icmp_seq=1 ttl=63 time=0.351 ms
  64 bytes from 64:ff9b::c000:201: icmp_seq=2 ttl=63 time=0.373 ms

  --- 64:ff9b::192.0.2.1 ping statistics ---
  2 packets transmitted, 2 received, 0% packet loss, time 1023ms
  rtt min/avg/max/mdev = 0.351/0.362/0.373/0.011 ms

.. start_vyoslinter
