.. _dhcp-relay:

##########
DHCP Relay
##########

If you want your router to forward DHCP requests to an external DHCP server
you can configure the system to act as a DHCP relay agent. The DHCP relay
agent works with IPv4 and IPv6 addresses.

All interfaces used for the DHCP relay must be configured. This includes the
uplink to the DHCP server.

**********
IPv4 relay
**********

Configuration
=============

.. cfgcmd:: set service dhcp-relay interface <interface>

   Interfaces that participate in the DHCP relay process. If this command is
   used, at least two entries of it are required: one for the interface that
   captures the dhcp-requests, and one for the interface to forward such
   requests. A warning message will be shown if this command is used, since
   new implementations should use ``listen-interface`` and
   ``upstream-interface``.

.. cfgcmd:: set service dhcp-relay listen-interface <interface>

   Interface for DHCP Relay Agent to listen for requests.

.. cfgcmd:: set service dhcp-relay upstream-interface <interface>

   Interface for DHCP Relay Agent to forward requests out.

.. cfgcmd:: set service dhcp-relay server <server>

   Configure IP address of the DHCP `<server>` which will handle the relayed
   packets.

.. cfgcmd:: set service dhcp-relay relay-options relay-agents-packets discard

   The router should discard DHCP packages already containing relay agent
   information to ensure that only requests from DHCP clients are forwarded.

.. cfgcmd:: set service dhcp-relay disable

   Disable dhcp-relay service.

Options
-------

.. cfgcmd:: set service dhcp-relay relay-options hop-count <count>

   Set the maximum hop `<count>` before packets are discarded. Range 0...255,
   default 10.

.. cfgcmd:: set service dhcp-relay relay-options max-size <size>

   Set maximum `<size>` of DHCP packets including relay agent information. If a
   DHCP packet size surpasses this value it will be forwarded without appending
   relay agent information. Range 64...1400, default 576.

.. cfgcmd:: set service dhcp-relay relay-options relay-agents-packets
   <append | discard | forward | replace>

   Four policies for reforwarding DHCP packets exist:

   * **append:** The relay agent is allowed to append its own relay information
     to a received DHCP packet, disregarding relay information already present
     in the packet.

   * **discard:** Received packets which already contain relay information will
     be discarded.

   * **forward:** All packets are forwarded, relay information already present
     will be ignored.

   * **replace:** Relay information already present in a packet is stripped and
     replaced with the router's own relay information set.

Example
=======

* Listen for DHCP requests on interface ``eth1``.
* DHCP server is located at IPv4 address 10.0.1.4 on ``eth2``.
* Router receives DHCP client requests on ``eth1`` and relays them to the
  server at 10.0.1.4 on ``eth2``.

.. figure:: /_static/images/service_dhcp-relay01.*
   :scale: 80 %
   :alt: DHCP relay example

   DHCP relay example

The generated configuration will look like:

.. code-block:: none

  show service dhcp-relay
      listen-interface eth1
      upstream-interface eth2
      server 10.0.1.4
      relay-options {
         relay-agents-packets discard
      }

Also, for backwards compatibility this configuration, which uses generic
interface definition, is still valid:

.. code-block:: none

  show service dhcp-relay
      interface eth1
      interface eth2
      server 10.0.1.4
      relay-options {
         relay-agents-packets discard
      }

Operation
=========

.. opcmd:: restart dhcp relay-agent

   Restart DHCP relay service

**********
IPv6 relay
**********

.. _dhcp-relay:ipv6_configuration:

Configuration
=============

.. cfgcmd:: set service dhcpv6-relay listen-interface <interface>

   Set eth1 to be the listening interface for the DHCPv6 relay.

   Multiple interfaces may be specified.

.. cfgcmd:: set service dhcpv6-relay upstream-interface <interface>
   address <server>

   Specifies an upstream network `<interface>` from which replies from
   `<server>` and other relay agents will be accepted.

.. _dhcp-relay:ipv6_options:

.. cfgcmd:: set service dhcpv6-relay disable

   Disable dhcpv6-relay service.

.. _dhcp_relay:v6_options:

Options
-------

.. cfgcmd:: set service dhcpv6-relay max-hop-count <count>

   Set maximum hop count before packets are discarded, default: 10

.. cfgcmd:: set service dhcpv6-relay use-interface-id-option

   If this is set the relay agent will insert the interface ID. This option is
   set automatically if more than one listening interfaces are in use.

.. _dhcp-relay:ipv6_example:

Example
=======

* DHCPv6 requests are received by the router on `listening interface` ``eth1``
* Requests are forwarded through ``eth2`` as the `upstream interface`
* External DHCPv6 server is at 2001:db8::4

.. figure:: /_static/images/service_dhcpv6-relay01.*
   :scale: 80 %
   :alt: DHCPv6 relay example

   DHCPv6 relay example

The generated configuration will look like:

.. code-block:: none

  commit
  show service dhcpv6-relay
      listen-interface eth1 {
      }
      upstream-interface eth2 {
         address 2001:db8::4
      }

.. _dhcp-relay:ipv6_op_cmd:

Operation
=========

.. opcmd:: restart dhcpv6 relay-agent

   Restart DHCPv6 relay agent immediately.
