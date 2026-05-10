.. _nat66:

############
NAT66(NPTv6)
############

.. TODO:: Convert raw command blocks in this file to cfgcmd/opcmd
   directives for command coverage tracking.

:abbr:`NPTv6 (IPv6-to-IPv6 Network Prefix Translation)` is an address 
translation technology based on IPv6 networks, used to convert an IPv6 
address prefix in an IPv6 message into another IPv6 address prefix. 
We call this address translation method NAT66. Devices that support the NAT66
function are called NAT66 devices, which can provide NAT66 source
and destination address translation functions.

Overview
========

Different NAT Types
-------------------

.. _source-nat66:

SNAT66
^^^^^^

:abbr:`SNPTv6 (Source IPv6-to-IPv6 Network Prefix Translation)` The conversion
function is mainly used in the following scenarios:

* A single internal network and external network. Use the NAT66 device to 
  connect a single internal network and public network, and the hosts in 
  the internal network use IPv6 address prefixes that only support 
  routing within the local range. When a host in the internal network
  accesses the external network, the source IPv6 address prefix in 
  the message will be converted into a global unicast IPv6 address 
  prefix by the NAT66 device.
* Redundancy and load sharing. There are multiple NAT66 devices at the edge
  of an IPv6 network to another IPv6 network. The path through the NAT66 
  device to another IPv6 network forms an equivalent route, and traffic 
  can be load-shared on these NAT66 devices. In this case, you 
  can configure the same source address translation rules on these 
  NAT66 devices, so that any NAT66 device can handle IPv6 traffic between 
  different sites.
* Multi-homed. In a multi-homed network environment, the NAT66 device 
  connects to an internal network and simultaneously connects to 
  different external networks. Address translation can be configured 
  on each external network side interface of the NAT66 device to 
  convert the same internal network address into different external
  network addresses, and realize the mapping of the same internal 
  address to multiple external addresses.

.. _destination-nat66:

DNAT66
^^^^^^

The :abbr:`DNPTv6 (Destination IPv6-to-IPv6 Network Prefix Translation)` 
destination address translation function is used in scenarios where the 
server in the internal network provides services to the external network,
such as providing Web services or FTP services to the external network. 
By configuring the mapping relationship between the internal server 
address and the external network address on the external network 
side interface of the NAT66 device, external network users can 
access the internal network server through the designated 
external network address.

Prefix Conversion
------------------

Source Prefix
^^^^^^^^^^^^^

Every SNAT66 rule has a translation command defined. The prefix defined
for the translation is the prefix used when the address information in
a packet is replaced.、

The :ref:`source-nat66` rule replaces the source address of the packet 
and calculates the converted address using the prefix specified in the rule.

Example:

* Convert the address prefix of a single `fc01::/64` network to `fc00::/64`
* Output from `eth0` network interface

.. code-block:: none

  set nat66 source rule 1 outbound-interface name 'eth0'
  set nat66 source rule 1 source prefix 'fc01::/64'
  set nat66 source rule 1 translation address 'fc00::/64'

Destination Prefix
^^^^^^^^^^^^^^^^^^

For the :ref:`destination-nat66` rule, the destination address of
the packet isreplaced by the address calculated from the specified 
address or prefix in the `translation address` command

Example:

* Convert the address prefix of a single `fc00::/64` network 
  to `fc01::/64`
* Input from `eth0` network interface

.. code-block:: none

  set nat66 destination rule 1 inbound-interface name 'eth0'
  set nat66 destination rule 1 destination address 'fc00::/64'
  set nat66 destination rule 1 translation address 'fc01::/64'

For the destination, groups can also be used instead of an address.

Example:

.. code-block:: none

  set firewall group ipv6-address-group ADR-INSIDE-v6 address fc00::1

  set nat66 destination rule 1 inbound-interface name 'eth0'
  set nat66 destination rule 1 destination group address-group ADR-INSIDE-v6
  set nat66 destination rule 1 translation address 'fc01::/64'

Configuration Examples
======================

Use the following topology to build a nat66 based isolated 
network between internal and external networks (dynamic prefix is 
not supported):

.. figure:: /_static/images/vyos_1_4_nat66_simple.*
   :alt: VyOS NAT66 Simple Configure

R1:

.. code-block:: none

  set interfaces ethernet eth0 ipv6 address autoconf
  set interfaces ethernet eth1 address 'fc01::1/64'
  set nat66 destination rule 1 destination address 'fc00:470:f1cd:101::/64'
  set nat66 destination rule 1 inbound-interface name 'eth0'
  set nat66 destination rule 1 translation address 'fc01::/64'
  set nat66 source rule 1 outbound-interface name 'eth0'
  set nat66 source rule 1 source prefix 'fc01::/64'
  set nat66 source rule 1 translation address 'fc00:470:f1cd:101::/64'

R2:

.. code-block:: none

  set interfaces bridge br1 address 'fc01::2/64'
  set interfaces bridge br1 member interface eth0
  set interfaces bridge br1 member interface eth1
  set protocols static route6 ::/0 next-hop fc01::1
  set service router-advert interface br1 prefix ::/0


Use the following topology to translate internal user local addresses
(``fc::/7``) to DHCPv6-PD provided prefixes from an ISP connected to
a VyOS HA pair.

.. figure:: /_static/images/vyos_1_5_nat66_dhcpv6_wdummy.*
   :alt: VyOS NAT66 DHCPv6 using a dummy interface

Configure both routers (a and b) for DHCPv6-PD via dummy interface:

.. stop_vyoslinter

.. code-block:: none

  set interfaces dummy dum1 description 'DHCPv6-PD NPT dummy'
  set interfaces bonding bond0 vif 20 dhcpv6-options pd 0 interface dum1 address '0'
  set interfaces bonding bond0 vif 20 dhcpv6-options pd 1 interface dum1 address '0'
  set interfaces bonding bond0 vif 20 dhcpv6-options pd 2 interface dum1 address '0'
  set interfaces bonding bond0 vif 20 dhcpv6-options pd 3 interface dum1 address '0'
  set interfaces bonding bond0 vif 20 dhcpv6-options rapid-commit
  commit

.. start_vyoslinter

Get the DHCPv6-PD prefixes from both routers:

.. code-block:: none

  trae@cr01a-vyos# run show interfaces dummy dum1 br
  Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down
  Interface        IP Address                        S/L  Description
  ---------        ----------                        ---  -----------
  dum1             2001:db8:123:b008::/64           u/u  DHCPv6-PD NPT dummy
                   2001:db8:123:b00a::/64
                   2001:db8:123:b00b::/64
                   2001:db8:123:b009::/64

  trae@cr01b-vyos# run show int dummy dum1 brief
  Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down
  Interface        IP Address                        S/L  Description
  ---------        ----------                        ---  -----------
  dum1             2001:db8:123:b00d::/64           u/u  DHCPv6-PD NPT dummy
                   2001:db8:123:b00c::/64
                   2001:db8:123:b00e::/64
                   2001:db8:123:b00f::/64

Configure the A-side router for NPTv6 using the prefixes above:

.. code-block:: none

  set nat66 source rule 10 description 'NPT to VLAN 10'
  set nat66 source rule 10 outbound-interface name 'bond0.20'
  set nat66 source rule 10 source prefix 'fd52:d62e:8011:a::/64'
  set nat66 source rule 10 translation address '2001:db8:123:b008::/64'
  set nat66 source rule 20 description 'NPT to VLAN 70'
  set nat66 source rule 20 outbound-interface name 'bond0.20'
  set nat66 source rule 20 source prefix 'fd52:d62e:8011:46::/64'
  set nat66 source rule 20 translation address '2001:db8:123:b009::/64'
  set nat66 source rule 30 description 'NPT to VLAN 200'
  set nat66 source rule 30 outbound-interface name 'bond0.20'
  set nat66 source rule 30 source prefix 'fd52:d62e:8011:c8::/64'
  set nat66 source rule 30 translation address '2001:db8:123:b00a::/64'
  set nat66 source rule 40 description 'NPT to VLAN 240'
  set nat66 source rule 40 outbound-interface name 'bond0.20'
  set nat66 source rule 40 source prefix 'fd52:d62e:8011:f0::/64'
  set nat66 source rule 40 translation address '2001:db8:123:b00b::/64'
  commit

Configure the B-side router for NPTv6 using the prefixes above:

.. code-block:: none

  set nat66 source rule 10 description 'NPT to VLAN 10'
  set nat66 source rule 10 outbound-interface name 'bond0.20'
  set nat66 source rule 10 source prefix 'fd52:d62e:8011:a::/64'
  set nat66 source rule 10 translation address '2001:db8:123:b00c::/64'
  set nat66 source rule 20 description 'NPT to VLAN 70'
  set nat66 source rule 20 outbound-interface name 'bond0.20'
  set nat66 source rule 20 source prefix 'fd52:d62e:8011:46::/64'
  set nat66 source rule 20 translation address '2001:db8:123:b00d::/64'
  set nat66 source rule 30 description 'NPT to VLAN 200'
  set nat66 source rule 30 outbound-interface name 'bond0.20'
  set nat66 source rule 30 source prefix 'fd52:d62e:8011:c8::/64'
  set nat66 source rule 30 translation address '2001:db8:123:b00e::/64'
  set nat66 source rule 40 description 'NPT to VLAN 240'
  set nat66 source rule 40 outbound-interface name 'bond0.20'
  set nat66 source rule 40 source prefix 'fd52:d62e:8011:f0::/64'
  set nat66 source rule 40 translation address '2001:db8:123:b00f::/64'
  commit

Verify that connections are hitting the rule on both sides:

.. code-block:: none

  trae@cr01a-vyos# run show nat66 source statistics
  Rule    Packets    Bytes    Interface
  ------  ---------  -------  -----------
  10      1          104      bond0.20
  20      1          104      bond0.20
  30      8093       669445   bond0.20
  40      2446       216912   bond0.20
