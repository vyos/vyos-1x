.. _routing-static-arp:
.. meta::
   :description: The Address Resolution Protocol (ARP) resolves 
                 network-layer addresses to link-layer MAC addresses.
   :keywords: arp, network, protocol, mac, address, ipv4, static

###
ARP
###

The :abbr:`ARP (Address Resolution Protocol)` resolves IPv4 network layer addresses
to link layer MAC addresses. 
addresses. This mapping is essential for communication within the Internet 
Protocol suite. ARP was standardized in 1982 by :rfc:`826` (STD 37).

.. note:: In Internet Protocol version 6 (IPv6) networks, address resolution is 
   performed by the Neighbor Discovery Protocol (NDP).

Use the following commands to configure or view ARP table entries.

Configuration
-------------

.. cfgcmd:: set protocols static arp interface <interface> address <host> mac <mac>

   **Configure a static ARP entry on the specified interface.**

   This creates a permanent mapping between an IP address and a MAC address 
   on the specified interface.

   Example:

   .. code-block:: none

      set protocols static arp interface eth0 address 192.0.2.1 mac 01:23:45:67:89:01

Operation
---------

.. opcmd:: show protocols static arp

   Show all ARP table entries across all interfaces.

   .. code-block:: none

      vyos@vyos:~$ show protocols static arp
      Address                  HWtype  HWaddress           Flags Mask     Iface
      10.1.1.1                 ether   00:53:00:de:23:2e   C              eth1
      10.1.1.100               ether   00:53:00:de:23:aa   CM             eth1

.. opcmd:: show protocols static arp interface <interface>

   Show all ARP table entries for the specific interface.

   Example for ``eth1``:

   .. code-block:: none

      vyos@vyos:~$ show protocols static arp interface eth1
      Address                  HWtype  HWaddress           Flags Mask     Iface
      10.1.1.1                 ether   00:53:00:de:23:2e   C              eth1
      10.1.1.100               ether   00:53:00:de:23:aa   CM             eth1

.. _ARP: https://en.wikipedia.org/wiki/Address_Resolution_Protocol