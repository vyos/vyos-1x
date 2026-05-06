.. _traffic-engineering:

###################
Traffic Engineering
###################

Traffic Engineering (TE) is possibility to send traffic from node to node using
alternative path.

Common link parameters
----------------------

Traffic Engineering parameters are used for both IS-IS and OSPF (not supported yet).

.. cfgcmd::  set protocols traffic-engineering admin-group <admin-group-name> bit-position <bit-position-value>

  Create Administrative group and assosiate bit position with it. These groups can be
  used in the following commands.

  <bit-position-value> can have value 0-31. There cannot be two groups with same bit position.

.. cfgcmd::  set protocols traffic-engineering interface <ifname> admin-group <admin-group-name>

  Set administrative group for interface <ifname>. Multiple values can be provided.

.. cfgcmd::  set protocols traffic-engineering interface <ifname> max-bandwidth <max-bandwidth-value-mbps>

  Set maximum bandwidth for interface <ifname>. Value given in Mbits per second.

.. cfgcmd::  set protocols traffic-engineering interface <ifname> max-reservable-bandwidth <max-reservable-bandwidth-value-mbps>

  Set maximum reservable bandwidth for interface <ifname>. Value given in Mbits per second.


IS-IS TE Configuration
----------------------

Traffic Engineering (TE) can be enabled and exported for IS-IS
using the following commands:

.. cfgcmd:: set protocols isis traffic-engineering enable

  Enable Traffic Engineering for IS-IS.

.. cfgcmd:: set protocols isis traffic-engineering export

  Export Traffic Engineering data to neighbors.

.. cfgcmd:: set protocols isis traffic-engineering address <ipv4-address>

  Configure IPv4 address for MPLS-TE.
