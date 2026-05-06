##################
Local Route Policy
##################

Policies for local traffic are defined in this section.

*************
Configuration
*************

Local Route IPv4
================

.. cfgcmd:: set policy local-route rule <1-32765> set table <1-200|main>

   Set the routing table to use for forwarding matching packets.

.. cfgcmd:: set policy local-route rule <1-32765> set vrf <vrf|default>

   Set the VRF to use for forwarding matching packets.

.. cfgcmd:: set policy local-route rule <1-32765> protocol <protocol>

   Match specified protocol (name or number).

.. cfgcmd:: set policy local-route rule <1-32765> fwmark <1-2147483647>

   Match specified firewall mark (fwmark).

.. cfgcmd:: set policy local-route rule <1-32765> source address <x.x.x.x|x.x.x.x/x>

   Match specified source address or prefix.

.. cfgcmd:: set policy local-route rule <1-32765> source port <1-65535>

   Match specified source port.

.. cfgcmd:: set policy local-route rule <1-32765> destination address <x.x.x.x|x.x.x.x/x>

   Match specified destination address or prefix.

.. cfgcmd:: set policy local-route rule <1-32765> destination port <1-65535>

   Match specified destination port.

.. cfgcmd:: set policy local-route rule <1-32765> inbound-interface <interface>

   Match specified inbound interface.

Local Route IPv6
================

.. cfgcmd:: set policy local-route6 rule <1-32765> set table <1-200|main>

   Set the routing table to use for forwarding matching packets.

.. cfgcmd:: set policy local-route6 rule <1-32765> set vrf <vrf|default>

   Set the VRF to use for forwarding matching packets.

.. cfgcmd:: set policy local-route6 rule <1-32765> protocol <protocol>

   Match specified protocol (name or number).

.. cfgcmd:: set policy local-route6 rule <1-32765> fwmark <1-2147483647>

   Match specified firewall mark (fwmark).

.. cfgcmd:: set policy local-route6 rule <1-32765> source address <h:h:h:h:h:h:h:h|h:h:h:h:h:h:h:h/x>

   Match specified source address or prefix.

.. cfgcmd:: set policy local-route6 rule <1-32765> source port <1-65535>

   Match specified source port.

.. cfgcmd:: set policy local-route6 rule <1-32765> destination address <h:h:h:h:h:h:h:h|h:h:h:h:h:h:h:h/x>

   Match specified destination address or prefix.

.. cfgcmd:: set policy local-route6 rule <1-32765> destination port <1-65535>

   Match specified destination port.

.. cfgcmd:: set policy local-route6 rule <1-32765> inbound-interface <interface>

   Match specified inbound interface.