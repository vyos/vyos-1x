.. _udp_broadcast_relay:

###################
UDP Broadcast Relay
###################

Certain vendors use broadcasts to identify their equipment within one ethernet
segment. Unfortunately if you split your network with multiple VLANs you loose
the ability of identifying your equipment.

This is where "UDP broadcast relay" comes into play! It will forward received
broadcasts to other configured networks.

Every UDP port which will be forward requires one unique ID. Currently we
support 99 IDs!

Configuration
-------------

.. cfgcmd:: set service broadcast-relay id <n> description <description>

   A description can be added for each and every unique relay ID. This is
   useful to distinguish between multiple different ports/applications.

.. cfgcmd:: set service broadcast-relay id <n> interface <interface>

   The interface used to receive and relay individual broadcast packets. If you
   want to receive/relay packets on both `eth1` and `eth2` both interfaces need
   to be added.

.. cfgcmd:: set service broadcast-relay id <n> address <ipv4-address>

   Set the source IP of forwarded packets, otherwise original senders address
   is used.

.. cfgcmd:: set service broadcast-relay id <n> port <port>

   The UDP port number used by your application. It is mandatory for this kind
   of operation.

.. cfgcmd:: set service broadcast-relay id <n> disable

   Each broadcast relay instance can be individually disabled without deleting
   the configured node by using the following command:

.. cfgcmd:: set service broadcast-relay disable

   In addition you can also disable the whole service without the need to remove
   it from the current configuration.

.. note:: You can run the UDP broadcast relay service on multiple routers
   connected to a subnet. There is **NO** UDP broadcast relay packet storm!

Example
-------

To forward all broadcast packets received on `UDP port 1900` on `eth3`, `eth4`
or `eth5` to all other interfaces in this configuration.

.. code-block:: none

  set service broadcast-relay id 1 description 'SONOS'
  set service broadcast-relay id 1 interface 'eth3'
  set service broadcast-relay id 1 interface 'eth4'
  set service broadcast-relay id 1 interface 'eth5'
  set service broadcast-relay id 1 port '1900'
