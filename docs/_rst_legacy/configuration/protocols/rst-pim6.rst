.. _pim6:

##############################################
PIM6 - Protocol Independent Multicast for IPv6
##############################################

VyOS facilitates IPv6 Multicast by supporting **PIMv6** and **MLD**.

PIMv6 (Protocol Independent Multicast for IPv6) must be configured in every
interface of every participating router. Every router must also have the
location of the Rendevouz Point manually configured.
Then, unidirectional shared trees rooted at the Rendevouz Point will
automatically be built for multicast distribution.

Traffic from multicast sources will go to the Rendezvous Point, and receivers
will pull it from a shared tree using MLD (Multicast Listener Discovery).

Multicast receivers will talk MLD to their local router, so, besides having
PIMv6 configured in every router, MLD must also be configured in any router
where there could be a multicast receiver locally connected.

VyOS supports both MLD version 1 and version 2
(which allows source-specific multicast).

Basic commands
==============
These are the commands for a basic setup.

.. cfgcmd:: set protocols pim6 interface <interface-name>

   Use this command to enable PIMv6 in the selected interface so that it
   can communicate with PIMv6 neighbors. This command also enables MLD reports
   and query on the interface unless :cfgcmd:`mld disable` is configured.

.. cfgcmd:: set protocols pim6 interface <interface-name> mld disable

   Disable MLD reports and query on the interface.


Tuning commands
===============
You can also tune multicast with the following commands.


.. cfgcmd:: set protocols pim6 interface <interface-name> mld interval <seconds>

   Use this command to configure in the selected interface the MLD
   host query interval (1-65535) in seconds that PIM will use.
   The default value is 125 seconds.

.. cfgcmd:: set protocols pim6 interface <interface-name> mld join <multicast-address>

   Use this command to allow the selected interface to join a multicast group.

.. cfgcmd:: set protocols pim6 interface <interface-name> mld join <multicast-address> source <source-address>

   Use this command to allow the selected interface to join a source-specific multicast
   group.

.. cfgcmd:: set protocols pim6 interface <interface-name> mld last-member-query-count <count>

   Set the MLD last member query count. The default value is 2.

.. cfgcmd:: set protocols pim6 interface <interface-name> mld last-member-query-interval <milliseconds>

   Set the MLD last member query interval in milliseconds (100-6553500). The default value is 1000 milliseconds.

.. cfgcmd:: set protocols pim6 interface <interface-name> mld max-response-time <milliseconds>

   Set the MLD query response timeout in milliseconds (100-6553500). The default value is 10000 milliseconds.

.. cfgcmd:: set protocols pim6 interface <interface-name> mld version <version-number>

   Set the MLD version used on this interface. The default value is 2.

*********************
Configuration Example
*********************

To enable MLD reports and query on interfaces `eth0` and `eth1`:

.. code-block:: none

  set protocols pim6 interface eth0
  set protocols pim6 interface eth1

The following configuration explicitly joins multicast group `ff15::1234` on interface `eth1`
and source-specific multicast group `ff15::5678` with source address `2001:db8::1` on interface
`eth1`:

.. code-block:: none

  set protocols pim6 interface eth0 mld join ff15::1234
  set protocols pim6 interface eth1 mld join ff15::5678 source 2001:db8::1
