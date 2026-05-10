:lastproofread: 2026-02-02

.. _geneve-interface:

######
Geneve
######

:abbr:`Geneve (Generic Network Virtualization Encapsulation)` interfaces 
operate as virtual network ports. Administrators can apply standard network 
configurations on them, such as IP addressing, bridging, or firewall rules, 
just as they would on physical Ethernet ports.

The Geneve protocol encapsulates Layer 2 Ethernet frames originating from 
endpoints such as virtual machines, containers, or physical servers inside UDP 
packets. It unifies the features of earlier encapsulation protocols, including 
VXLAN, NVGRE, and STT, and addresses their limitations, such as fixed header 
structures and a lack of metadata support. Because of its extensibility, Geneve 
may eventually replace those older protocols.

Geneve tunnels are used to connect virtual switches residing within 
hypervisors, physical switches, middleboxes, and other network appliances.

Geneve tunnels operate over any standard IP network. In larger deployments, 
the underlying network (underlay) is often built using a **Clos** topology, 
also known as a *leaf-and-spine* or *fat-tree* topology.

Geneve header:

.. code-block:: none

  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |Ver|  Opt Len  |O|C|    Rsvd.  |          Protocol Type        |
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |        Virtual Network Identifier (VNI)       |    Reserved   |
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |                    Variable Length Options                    |
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

*************
Configuration
*************

Common interface configuration
==============================

.. cmdinclude:: /_include/interface-address.txt
  :var0: geneve
  :var1: gnv0

.. cmdinclude:: /_include/interface-description.txt
  :var0: geneve
  :var1: gnv0

.. cmdinclude:: /_include/interface-disable.txt
  :var0: geneve
  :var1: gnv0

.. cmdinclude:: /_include/interface-mac.txt
  :var0: geneve
  :var1: gnv0

.. cmdinclude:: /_include/interface-mtu.txt
  :var0: geneve
  :var1: gnv0

.. cmdinclude:: /_include/interface-ip.txt
  :var0: geneve
  :var1: gnv0

.. cmdinclude:: /_include/interface-ipv6.txt
  :var0: geneve
  :var1: gnv0

Geneve options
==============

.. cfgcmd:: set interfaces geneve gnv0 remote <address>

   Configure the remote endpoint IP address for the Geneve tunnel.

.. cfgcmd:: set interfaces geneve gnv0 vni <vni>

   **Configure** :abbr:`VNI (Virtual Network Identifier)` **for the Geneve 
   interface.**

   The VNI is a virtual network identifier. It allows multiple virtual networks to 
   share the same physical infrastructure and remain isolated.

   The VNI is also used to distribute traffic after it leaves the tunnel, for 
   example, to map packets with overlapping IP addresses to specific routing 
   tables.

.. cfgcmd:: set interfaces gnv0 <interface> port <port>

   **Configure the destination UDP port for the remote Geneve tunnel endpoint.**

   Ensure the remote peer is configured to listen on this specific port.


