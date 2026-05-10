:lastproofread: 2026-03-30

.. _firewall-flowtables-configuration:

#################################
Flowtables Firewall Configuration
#################################

.. include:: /_include/need_improvement.txt

********
Overview
********

This section provides information on firewall configuration for flowtables.

.. cfgcmd:: set firewall flowtable ...

To learn about the general traffic flow in VyOS firewalls,
see :doc:`Firewall </configuration/firewall/index>`.

.. code-block:: none

   - set firewall
       * flowtable
            - custom_flow_table
               + ...


Flowtables let you define a fastpath through the flowtable datapath.
Flowtables support layer 3 (IPv4 and IPv6) and layer 4 (TCP and UDP)
protocols.

.. figure:: /_static/images/firewall-flowtable-packet-flow.*

After the first packet successfully traverses the IP forwarding path (black
circles path), you can offload subsequent packets to the flowtable through your
ruleset. You specify when to add a flow to the flowtable during forward
filtering (red circle number 6).

When a packet finds a matching entry in the flowtable (flowtable hit), the
system transmits it to the output netdevice. This means packets bypass the
classic IP forwarding path and use the **Fast Path** (orange circles path).
As a result, you do not see these packets from any Netfilter hooks after
ingress. If no matching entry exists in the flowtable (flowtable miss), the
packet traverses the classic IP forwarding path.

.. note:: **Flowtable Reference:**
   https://docs.kernel.org/networking/nf_flowtable.html


***********************
Flowtable Configuration
***********************

To use flowtables, you need to configure the following:

   * Create a flowtable that includes the interfaces
     that are going to be used by the flowtable.

   * Create a firewall rule. Set the action to
     ``offload`` and use your desired flowtable for ``offload-target``.

Creating a flow table:

.. cfgcmd:: set firewall flowtable <flow_table_name> interface <iface>

   Specify interfaces to use in the flowtable.

.. cfgcmd:: set firewall flowtable <flow_table_name> description <text>

Provide a description for the flow table.

.. cfgcmd:: set firewall flowtable <flow_table_name> offload
   <hardware | software>

   Specify the offload type the flowtable uses: ``hardware`` or
   ``software``. The default is ``software`` offload.

.. note:: **Hardware offload**: Make sure your network interface controller
   (NIC) supports hardware offloading and that you have the necessary drivers
    installed before enabling this option.

Creating rules for using flow tables:

.. cfgcmd:: set firewall [ipv4 | ipv6] forward filter rule <1-999999>
   action offload

   Create a firewall rule in the forward chain with the action set to
   ``offload``.

.. cfgcmd:: set firewall [ipv4 | ipv6] forward filter rule <1-999999>
   offload-target <flowtable>

   Create a firewall rule in the forward chain and specify which flowtable
   to use. Only applicable if the action is ``offload``.

*********************
Configuration Example
*********************

Consider the following in this setup:

   * This example uses two interfaces in the flowtables: ``eth0`` and ``eth1``.

   * The example provides a minimal firewall ruleset with filtering rules
     and rules for using flowtable offload capabilities.

The first packet is evaluated by the firewall path, so a
desired connection should be explicitly accepted.
The same should occur for traffic in reverse order.
In most cases, state policies are
used to accept a connection in the reverse path.

In the following example only traffic coming from interface ``eth0``,
TCP protocol, and destination port 1122 is accepted.
All other traffic to the router is dropped.

Commands
--------

.. code-block:: none

      set firewall flowtable FT01 interface 'eth0'
      set firewall flowtable FT01 interface 'eth1'
      set firewall ipv4 forward filter default-action 'drop'
      set firewall ipv4 forward filter rule 10 action 'offload'
      set firewall ipv4 forward filter rule 10 offload-target 'FT01'
      set firewall ipv4 forward filter rule 10 state 'established'
      set firewall ipv4 forward filter rule 10 state 'related'
      set firewall ipv4 forward filter rule 20 action 'accept'
      set firewall ipv4 forward filter rule 20 state 'established'
      set firewall ipv4 forward filter rule 20 state 'related'
      set firewall ipv4 forward filter rule 110 action 'accept'
      set firewall ipv4 forward filter rule 110 destination address '192.0.2.100'
      set firewall ipv4 forward filter rule 110 destination port '1122'
      set firewall ipv4 forward filter rule 110 inbound-interface name 'eth0'
      set firewall ipv4 forward filter rule 110 protocol 'tcp'

Explanation
-----------

Here's what happens for a desired connection:

   1. A packet arrives on ``eth0`` with destination address ``192.0.2.100``, TCP
      protocol, and destination port 1122. Assume this address is reachable
      through interface ``eth1``.

   2. For this first packet, the connection state is **new**. Neither rule 10
      nor rule 20 applies.

   3. Rule 110 matches, so the connection is accepted.

   4. When the server 192.0.2.100 replies, the connection state becomes
      **established**, and rule 20 accepts the reply.

   5. The router receives the second packet for this connection. Because the
      connection state is **established**, rule 10 matches and adds a new
      entry in the flowtable FT01 for this connection.

   6. Subsequent packets skip the traditional path and use the **Fast Path**
      for offloading.

Checks
------

Check the conntrack table to verify that the system accepted and properly
offloaded connections.

.. code-block:: none

      vyos@FlowTables:~$ show firewall ipv4 forward filter
      Ruleset Information
      
      ---------------------------------
      ipv4 Firewall "forward filter"
      
      Rule     Action    Protocol      Packets    Bytes  Conditions
      -------  --------  ----------  ---------  -------  ----------------------------------------------------------------
      10       offload   all                 8      468  ct state { established, related }  flow add @VYOS_FLOWTABLE_FT01
      20       accept    all                 8      468  ct state { established, related }  accept
      110      accept    tcp                 2      120  ip daddr 192.0.2.100 tcp dport 1122 iifname "eth0"  accept
      default  drop      all                 7      420
      
      vyos@FlowTables:~$ sudo conntrack -L | grep tcp
      conntrack v1.4.6 (conntrack-tools): 5 flow entries have been shown.
      tcp      6 src=198.51.100.100 dst=192.0.2.100 sport=41676 dport=1122 src=192.0.2.100 dst=198.51.100.100 sport=1122 dport=41676 [OFFLOAD] mark=0 use=2
      vyos@FlowTables:~$
