:lastproofread: 2026-03-05

.. _pseudo-ethernet-interface:

#########################
MACVLAN (pseudo-Ethernet)
#########################

MACVLAN, or pseudo-Ethernet interfaces, operate as logical subinterfaces of 
standard Ethernet interfaces. Each subinterface has a unique MAC address but 
shares a single physical Ethernet port.
That allows the user to send packets from different source IPv4 or IPv6 addresses
using a different MAC address.


Pseudo-Ethernet interfaces behave like physical Ethernet interfaces. They 
support IPv4 and IPv6 addressing, can obtain IP addresses through DHCP or 
DHCPv6, and are mapped to a physical Ethernet port. They inherit 
characteristics such as speed and duplex from their parent interface and can 
be referenced like standard Ethernet interfaces once created. 


Pseudo-Ethernet interfaces may not work in environments that require a 
  :abbr:`NIC (Network Interface Card)` to have only one MAC address. 
  This includes:

  * VMware machines with default settings.
  * Network switches that permit only a single MAC address.
  * xDSL modems that learn the NIC's MAC address.

*************
Configuration
*************

Common interface configuration
==============================

.. cmdinclude:: /_include/interface-common-with-dhcp.txt
   :var0: pseudo-ethernet
   :var1: peth0

MACVLAN (pseudo-Ethernet) options
=================================

.. cfgcmd:: set interfaces pseudo-ethernet <interface> source-interface <ethX>

   Assign a physical Ethernet interface to the specified pseudo-Ethernet interface.

VLAN
====

.. cmdinclude:: /_include/interface-vlan-8021q.txt
   :var0: pseudo-ethernet
   :var1: peth0
