:lastproofread: 2023-11-13

.. _igmp_proxy:

##########
IGMP Proxy
##########

:abbr:`IGMP (Internet Group Management Protocol)` proxy sends IGMP host messages
on behalf of a connected client. The configuration must define one, and only one
upstream interface, and one or more downstream interfaces.

Configuration
=============

.. cfgcmd:: set protocols igmp-proxy interface <interface> role
   <upstream | downstream>

   * **upstream:** The upstream network interface is the outgoing interface
     which is responsible for communicating to available multicast data sources.
     There can only be one upstream interface.

   * **downstream:** Downstream network interfaces are the distribution
     interfaces to the destination networks, where multicast clients can join
     groups and receive multicast data. One or more downstream interfaces must
     be configured.

.. cfgcmd:: set protocols igmp-proxy interface <interface> alt-subnet <network>

   Defines alternate sources for multicasting and IGMP data. The network address
   must be on the following format 'a.b.c.d/n'. By default, the router will
   accept data from sources on the same network as configured on an interface.
   If the multicast source lies on a remote network, one must define from where
   traffic should be accepted.

   This is especially useful for the upstream interface, since the source for
   multicast traffic is often from a remote location.

   This option can be supplied multiple times.

.. cfgcmd:: set protocols igmp-proxy disable-quickleave

   Disables quickleave mode. In this mode the daemon will not send a Leave IGMP
   message upstream as soon as it receives a Leave message for any downstream
   interface. The daemon will not ask for Membership reports on the downstream
   interfaces, and if a report is received the group is not joined again the
   upstream.

   If it's vital that the daemon should act exactly like a real multicast client
   on the upstream interface, this function should be enabled.

   Enabling this function increases the risk of bandwidth saturation.

.. cfgcmd:: set protocols igmp-proxy disable

   Disable this service.

.. _igmp:proxy_example:

Example
-------

Interface `eth1` LAN is behind NAT. In order to subscribe `10.0.0.0/23` subnet
multicast which is in `eth0` WAN we need to configure igmp-proxy.

.. code-block:: none

  set protocols igmp-proxy interface eth0 role upstream
  set protocols igmp-proxy interface eth0 alt-subnet 10.0.0.0/23
  set protocols igmp-proxy interface eth1 role downstream

Operation
=========

.. opcmd:: restart igmp-proxy

   Restart the IGMP proxy process.
