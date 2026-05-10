:lastproofread: 2026-02-05

.. _l2tpv3-interface:

######
L2TPv3
######    

:abbr:`L2TPv3 (Layer 2 Tunneling Protocol version 3)` interfaces let you 
establish L2TPv3 tunnels to transport Layer 2 traffic over IP networks.

The L2TPv3 protocol (defined in RFC 3931) wraps Layer 2 frames (e.g., Ethernet, 
Frame Relay, HDLC) within IP packets, allowing them to traverse the underlying 
IP infrastructure.

Unlike L2TPv2, which strictly requires UDP encapsulation, the L2TPv3 protocol 
is more flexible and supports two encapsulation types:

 * **Direct IP:** Tunnel data is encapsulated directly inside IP packets 
   (Protocol 115) for lower overhead.
 * **UDP:** Tunnel data is encapsulated inside a UDP datagram. This allows the 
   tunnel to traverse NAT more easily.

L2TPv3 tunnels connect geographically separated sites, serving as a simpler 
alternative to :ref:`mpls` by operating over basic IP connectivity rather than 
requiring a full MPLS infrastructure.

L2TPv3 tunnels can be established over both IPv4 and IPv6 underlying networks.

*************
Configuration
*************

Common interface configuration
==============================

.. cmdinclude:: /_include/interface-common-without-dhcp.txt
   :var0: l2tpv3
   :var1: l2tpeth0

L2TPv3 options
==============

Use the following commands to configure the L2TPv3 tunnel's specific parameters.

.. cfgcmd:: set interfaces l2tpv3 <interface> encapsulation <udp | ip>

  **Configure the encapsulation type for the L2TPv3 tunnel.**

  Valid values are ``udp`` and ``ip``.

  The default encapsulation type is ``udp``.

.. note:: The encapsulation type must match on both the local and remote peers 
   for the tunnel to establish. 

.. cfgcmd:: set interfaces l2tpv3 <interface> source-address <address>

  **Configure the L2TPv3 tunnel source IP address.**

  The specified address must be a local interface IP address and can be either 
  IPv4 or IPv6.

.. cfgcmd:: set interfaces l2tpv3 <interface> remote <address>

  **Configure the L2TPv3 tunnel destination IP address.** 

  The specified address must be a remote peer’s interface IP address and can be 
  either IPv4 or IPv6.

.. cfgcmd:: set interfaces l2tpv3 <interface> session-id <id>

  **Configure the local session ID within the L2TPv3 tunnel.**

  The ``session-id`` is a 32-bit value that identifies an incoming tunnel session
  on the local peer.

  The ``peer-session-id`` that identifies this session on the remote peer must be 
  set to the same value.

.. cfgcmd:: set interfaces l2tpv3 <interface> peer-session-id <id>

  **Configure the peer session ID within the L2TPv3 tunnel.** 

  The ``peer-session-id`` is a 32-bit value that identifies an outgoing tunnel 
  session from the local peer. 

  The ``peer-session-id`` must match the ``session-id`` configured for this 
  session on the remote peer.

.. cfgcmd:: set interfaces l2tpv3 <interface> tunnel-id <id>

  **Configure the local identifier for the L2TPv3 tunnel.**

  The ``tunnel-id`` is a 32-bit value that identifies the L2TPv3 tunnel on the 
  local peer.

  The ``peer-tunnel-id`` that identifies this tunnel on the remote peer must be 
  set to the same value.

.. cfgcmd:: set interfaces l2tpv3 <interface> peer-tunnel-id <id>

  **Configure the peer identifier for the L2TPv3 tunnel.** 

  The ``peer-tunnel-id`` is a 32-bit value that identifies the L2TPv3 tunnel on 
  the remote peer and must correspond to the ``tunnel-id`` configured for that 
  tunnel on that peer.
  
  The ``peer-tunnel-id`` must match the ``tunnel-id`` that identifies this tunnel 
  on the remote peer.

*******
Example
*******

L2TPv3 tunnel with IP encapsulation
===================================

The following example shows the configuration of an L2TPv3 tunnel using direct 
IP encapsulation:

.. code-block:: none

  # show interfaces l2tpv3
  l2tpv3 l2tpeth10 {
      address 192.168.37.1/27
      encapsulation ip
      source-address 192.0.2.1
      peer-session-id 100
      peer-tunnel-id 200
      remote 203.0.113.24
      session-id 100
      tunnel-id 200
  }

The inverse configuration must be applied to the remote peer.

L2TPv3 tunnel with UDP encapsulation 
====================================

The following example shows the configuration of an L2TPv3 tunnel using UDP 
encapsulation. 

This setup is recommended when the tunnel traverses NAT devices.

Configuration notes:

* Use a local LAN IP address as the ``source-address``.
* Configure a forwarding rule to allow tunnel traffic on the specified UDP port 
  on the upstream NAT device.
* Use a distinct UDP port for each individual tunnel.

.. code-block:: none

  # show interfaces l2tpv3
  l2tpv3 l2tpeth10 {
      address 192.168.37.1/27
      destination-port 9001
      encapsulation udp
      source-address 192.0.2.1
      peer-session-id 100
      peer-tunnel-id 200
      remote 203.0.113.24
      session-id 100
      source-port 9000
      tunnel-id 200
  }
