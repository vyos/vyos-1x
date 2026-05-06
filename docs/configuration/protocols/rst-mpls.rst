.. _mpls:

####
MPLS
####

:abbr:`MPLS (Multi-Protocol Label Switching)` is a packet forwarding paradigm
which differs from regular IP forwarding. Instead of IP addresses being used to
make the decision on finding the exit interface, a router will instead use an
exact match on a 32 bit/4 byte header called the MPLS label. This label is
inserted between the ethernet (layer 2) header and the IP (layer 3) header.
One can statically or dynamically assign label allocations, but we will focus
on dynamic allocation of labels using some sort of label distribution protocol
(such as the aptly named Label Distribution Protocol / LDP, Resource Reservation
Protocol / RSVP, or Segment Routing through OSPF/ISIS). These protocols allow
for the creation of a unidirectional/unicast path called a labeled switched
path (initialized as LSP) throughout the network that operates very much like
a tunnel through the network. An easy way of thinking about how an MPLS LSP
actually forwards traffic throughout a network is to think of a GRE tunnel.
They are not the same in how they operate, but they are the same in how they
handle the tunneled packet. It would be good to think of MPLS as a tunneling
technology that can be used to transport many different types of packets, to
aid in traffic engineering by allowing one to specify paths throughout the
network (using RSVP or SR), and to generally allow for easier intra/inter
network transport of data packets.

For more information on how MPLS label switching works, please go visit
`Wikipedia (MPLS)`_.

.. note:: MPLS support in VyOS is not finished yet, and therefore its 
  functionality is limited. Currently there is no support for MPLS enabled VPN
  services such as L2VPNs and mVPNs. RSVP support is also not present as the
  underlying routing stack (FRR) does not implement it. Currently VyOS 
  implements LDP as described in RFC 5036; other LDP standard are the 
  following ones: RFC 6720, RFC 6667, RFC 5919, RFC 5561, RFC 7552, RFC 4447. 
  Because MPLS is already available (FRR also supports RFC 3031).


Label Distribution Protocol
===========================

The :abbr:`MPLS (Multi-Protocol Label Switching)` architecture does not assume
a single protocol to create MPLS paths. VyOS supports the Label Distribution
Protocol (LDP) as implemented by FRR, based on :rfc:`5036`.

:abbr:`LDP (Label Distribution Protocol)` is a TCP based MPLS signaling protocol
that distributes labels creating MPLS label switched paths in a dynamic manner.
LDP is not a routing protocol, as it relies on other routing protocols for
forwarding decisions. LDP cannot bootstrap itself, and therefore relies on said
routing protocols for communication with other routers that use LDP.

In order to allow for LDP on the local router to exchange label advertisements
with other routers, a TCP session will be established between automatically
discovered and statically assigned routers. LDP will try to establish a TCP
session to the **transport address** of other routers. Therefore for LDP to
function properly please make sure the transport address is shown in the
routing table and reachable to traffic at all times.

It is highly recommended to use the same address for both the LDP router-id and
the discovery transport address, but for VyOS MPLS LDP to work both parameters
must be explicitly set in the configuration.

Another thing to keep in mind with LDP is that much like BGP, it is a protocol
that runs on top of TCP. It however does not have an ability to do something
like a refresh capability like BGPs route refresh capability. Therefore one
might have to reset the neighbor for a capability change or a configuration
change to work.

Configuration Options
=====================

.. cfgcmd:: set protocols mpls interface <interface>

  Use this command to enable MPLS processing on the interface you define.

.. cfgcmd:: set protocols mpls ldp interface <interface>

  Use this command to enable LDP on the interface you define.

.. cfgcmd:: set protocols mpls ldp router-id <address>

  Use this command to configure the IP address used as the LDP router-id of the
  local device.

.. cfgcmd:: set protocols mpls ldp discovery transport-ipv4-address <address>
.. cfgcmd:: set protocols mpls ldp discovery transport-ipv6-address <address>

  Use this command to set the IPv4 or IPv6 transport-address used by LDP.

.. cfgcmd:: set protocols mpls ldp neighbor <address> password <password>

  Use this command to configure authentication for LDP peers. Set the
  IP address of the LDP peer and a password that should be shared in
  order to become neighbors.

.. cfgcmd:: set protocols mpls ldp neighbor <address> session-holdtime <seconds>

  Use this command to configure a specific session hold time for LDP peers.
  Set the IP address of the LDP peer and a session hold time that should be
  configured for it. You may have to reset the neighbor for this to work.

.. cfgcmd:: set protocols mpls ldp neighbor <address> ttl-security
  <disable | hop count>

  Use this command to enable, disable, or specify hop count for TTL security
  for LDP peers. By default the value is set to 255 (or max TTL).

.. cfgcmd:: set protocols mpls ldp discovery hello-ipv4-interval <seconds>
.. cfgcmd:: set protocols mpls ldp discovery hello-ipv4-holdtime <seconds>
.. cfgcmd:: set protocols mpls ldp discovery hello-ipv6-interval <seconds>
.. cfgcmd:: set protocols mpls ldp discovery hello-ipv6-holdtime <seconds>

  Use these commands if you would like to set the discovery hello and hold time
  parameters.

.. cfgcmd:: set protocols mpls ldp discovery session-ipv4-holdtime <seconds>
.. cfgcmd:: set protocols mpls ldp discovery session-ipv6-holdtime <seconds>

  Use this command if you would like to set the TCP session hold time intervals.

.. cfgcmd:: set protocols mpls ldp import ipv4 import-filter filter-access-list
  <access list number>
.. cfgcmd:: set protocols mpls ldp import ipv6 import-filter filter-access-list6
  <access list number>

  Use these commands to control the importing of forwarding equivalence classes
  (FECs) for LDP from neighbors. This would be useful for example on only
  accepting the labeled routes that are needed and not ones that are not
  needed, such as accepting loopback interfaces and rejecting all others.

.. cfgcmd:: set protocols mpls ldp export ipv4 export-filter filter-access-list
  <access list number>
.. cfgcmd:: set protocols mpls ldp export ipv6 export-filter filter-access-list6
  <access list number>

  Use these commands to control the exporting of forwarding equivalence classes
  (FECs) for LDP to neighbors. This would be useful for example on only
  announcing the labeled routes that are needed and not ones that are not
  needed, such as announcing loopback interfaces and no others.

.. cfgcmd:: set protocols mpls ldp export ipv4 explicit-null
.. cfgcmd:: set protocols mpls ldp export ipv6 explicit-null

  Use this command if you would like for the router to advertise FECs with a
  label of 0 for explicit null operations.

.. cfgcmd:: set protocols mpls ldp allocation ipv4 access-list
  <access list number>
.. cfgcmd:: set protocols mpls ldp allocation ipv6 access-list6
  <access list number>

  Use this command if you would like to control the local FEC allocations for
  LDP. A good example would be for your local router to not allocate a label for
  everything. Just a label for what it's useful. A good example would be just a
  loopback label.

.. cfgcmd:: set protocols mpls ldp parameters cisco-interop-tlv

  Use this command to use a Cisco non-compliant format to send and interpret
  the Dual-Stack capability TLV for IPv6 LDP communications. This is related to
  :rfc:`7552`.

.. cfgcmd:: set protocols mpls ldp parameters ordered-control

  Use this command to use ordered label distribution control mode. FRR
  by default uses independent label distribution control mode for label
  distribution.  This is related to :rfc:`5036`.

.. cfgcmd:: set protocols mpls ldp parameters transport-prefer-ipv4

  Use this command to prefer IPv4 for TCP peer transport connection for LDP
  when both an IPv4 and IPv6 LDP address are configured on the same interface.

.. cfgcmd:: set protocols mpls ldp targeted-neighbor ipv4 enable
.. cfgcmd:: set protocols mpls ldp targeted-neighbor ipv6 enable

  Use this command to enable targeted LDP sessions to the local router. The
  router will then respond to any sessions that are trying to connect to it that
  are not a link local type of TCP connection.

.. cfgcmd:: set protocols mpls ldp targeted-neighbor ipv4 address <address>
.. cfgcmd:: set protocols mpls ldp targeted-neighbor ipv6 address <address>

  Use this command to enable the local router to try and connect with a targeted
  LDP session to another router.

.. cfgcmd:: set protocols mpls ldp targeted-neighbor ipv4 hello-holdtime
  <seconds>
.. cfgcmd:: set protocols mpls ldp targeted-neighbor ipv4 hello-interval
  <seconds>
.. cfgcmd:: set protocols mpls ldp targeted-neighbor ipv6 hello-holdtime
  <seconds>
.. cfgcmd:: set protocols mpls ldp targeted-neighbor ipv6 hello-interval
  <seconds>

  Use these commands if you would like to set the discovery hello and hold time
  parameters for the targeted LDP neighbors.


Sample configuration to setup LDP on VyOS
-----------------------------------------

.. code-block:: none

  set protocols ospf area 0 network '192.168.255.252/32'                      <--- Routing for loopback
  set protocols ospf area 0 network '192.168.0.5/32'                          <--- Routing for an interface connecting to the network
  set protocols ospf parameters router-id '192.168.255.252'                   <--- Router ID setting for OSPF
  set protocols mpls interface 'eth1'                                         <--- Enable MPLS for an interface connecting to network
  set protocols mpls ldp discovery transport-ipv4-address '192.168.255.252'   <--- Transport address for LDP for TCP sessions to connect to
  set protocols mpls ldp interface 'eth1'                                     <--- Enable LDP for an interface connecting to network
  set protocols mpls ldp interface 'lo'                                       <--- Enable LDP on loopback for future services connectivity
  set protocols mpls ldp router-id '192.168.255.252'                          <--- Router ID setting for LDP
  set interfaces ethernet eth1 address '192.168.0.5/31'                       <--- Interface IP for connecting to network
  set interfaces loopback lo address '192.168.255.252/32'                     <--- Interface loopback IP for router ID and other uses


Operational Mode Commands
=========================

When LDP is working, you will be able to see label information in the outcome
of ``show ip route``. Besides that information, there are also specific *show*
commands for LDP:

Show
----

.. opcmd:: show mpls ldp binding

  Use this command to see the Label Information Base.

.. opcmd:: show mpls ldp discovery

  Use this command to see discovery hello information

.. opcmd:: show mpls ldp interface

  Use this command to see LDP interface information

.. opcmd:: show mpls ldp neighbor

  Use this command to see LDP neighbor information

.. opcmd:: show mpls ldp neighbor detail

  Use this command to see detailed LDP neighbor information

Reset
-----

.. opcmd:: reset mpls ldp neighbor <IPv4 or IPv6 address>

  Use this command to reset an LDP neighbor/TCP session that is established


.. stop_vyoslinter

.. _`Wikipedia (MPLS)`: https://en.wikipedia.org/wiki/Multiprotocol_Label_Switching

.. start_vyoslinter