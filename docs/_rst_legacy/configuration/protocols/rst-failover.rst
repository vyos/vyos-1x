:description: Failover routes are static routes that are installed in the routing
   table only while a configured health-check target responds. VyOS uses them
   to switch traffic to a backup path when the primary next hop becomes
   unreachable, and to restore the primary path automatically once it recovers.
:keywords: failover, failover route, static route, health check, icmp probe,
   next hop, route metric

########
Failover
########

Failover routes are manually configured network paths used only while their
health-check targets are reachable. If the target stops responding, VyOS
removes the route from the routing table and reinstalls it once the target
recovers.

*************
Configuration
*************

Use the following commands to configure failover routes for a specific remote
``<subnet>`` reachable via next-hop ``<address>``.

.. cfgcmd:: set protocols failover route <subnet> next-hop <address> check target <target-address>

   **Configure the health check target IP address.**

   This is typically a highly available host, either within the destination
   subnet or on the public internet.

   Example:

   .. code-block:: none

      set protocols failover route 203.0.113.1/32 next-hop 10.217.37.254 check target 8.8.8.8

.. cfgcmd:: set protocols failover route <subnet> next-hop <address> check timeout <timeout>

   **Configure the timeout interval, in seconds, between target health checks.**

   The valid range is 1 to 300 seconds. The default is 10 seconds.

   Example:

   .. code-block:: none

      set protocols failover route 203.0.113.1/32 next-hop 10.217.37.254 check timeout 2

.. cfgcmd:: set protocols failover route <subnet> next-hop <address> check type <protocol>

   **Configure the protocol to use for health checks.**

   The following protocols are available:

   * ``icmp``: VyOS sends two ICMP echo request packets with a 1-second
     response timeout. The health check is successful if at least one response
     is received.
   * ``arp``: VyOS sends two ARP requests with a 1-second response timeout.
     The health check is successful if at least one response is received.
   * ``tcp``: VyOS verifies whether the destination TCP port is open. The
     health check is successful if a TCP connection is successfully
     established with the target port.

   The default protocol is ``icmp``.

   .. note::

      When the check type is set to ``tcp``, you must also define the target
      TCP port.

   Example:

   .. code-block:: none

      set protocols failover route 203.0.113.1/32 next-hop 10.217.37.254 check type tcp

.. cfgcmd:: set protocols failover route <subnet> next-hop <address> check port <port>

   **Configure the destination TCP port on the health check target.**

   This parameter applies only when the check type is configured as ``tcp``.

   The valid port range is 1 to 65535.

   Example:

   .. code-block:: none

      set protocols failover route 203.0.113.1/32 next-hop 10.217.37.254 check port 443

.. cfgcmd:: set protocols failover route <subnet> next-hop <address> check policy <policy>

   **Configure the health check success policy for multiple targets.**

   The following policies are available:

   * ``any-available``: The health check succeeds if at least one of the
     configured targets responds successfully.
   * ``all-available``: The health check succeeds only if every configured
     target responds successfully.

   The default policy is ``any-available``.

   Example:

   .. code-block:: none

      set protocols failover route 203.0.113.1/32 next-hop 10.217.37.254 check policy all-available

.. cfgcmd:: set protocols failover route <subnet> next-hop <address> interface <interface>

   **Configure the local interface used to reach the next-hop address.**

   This parameter is mandatory.

   Example:

   .. code-block:: none

      set protocols failover route 203.0.113.1/32 next-hop 10.217.37.254 interface eth0

.. cfgcmd:: set protocols failover route <subnet> next-hop <address> metric <1-255>

   **Configure the metric (cost) for the failover route.**

   The metric defines the route priority. A lower metric value indicates a
   more preferred route.

   The default value is 1.

   Example:

   .. code-block:: none

      set protocols failover route 203.0.113.1/32 next-hop 10.217.37.254 metric 50

.. cfgcmd:: set protocols failover route <subnet> next-hop <address> onlink

   Configure the next-hop to be reachable via the assigned interface, even
   when ``<address>`` is outside any subnet configured on that interface.

   Example:

   .. code-block:: none

      set protocols failover route 203.0.113.1/32 next-hop 10.217.37.254 onlink

********
Examples
********

Failover route with a single next-hop and ICMP health check
===========================================================

The following example configures a failover route to ``203.0.113.1/32``
through next-hop ``192.0.2.1`` on ``eth0``. The next-hop is monitored with
ICMP probes to ``192.0.2.1`` every 5 seconds, and the route is installed with
a metric of 10.

.. code-block:: none

   set protocols failover route 203.0.113.1/32 next-hop 192.0.2.1 check target '192.0.2.1'
   set protocols failover route 203.0.113.1/32 next-hop 192.0.2.1 check timeout '5'
   set protocols failover route 203.0.113.1/32 next-hop 192.0.2.1 check type 'icmp'
   set protocols failover route 203.0.113.1/32 next-hop 192.0.2.1 interface 'eth0'
   set protocols failover route 203.0.113.1/32 next-hop 192.0.2.1 metric '10'

Verify the route:

.. code-block:: none

   vyos@vyos:~$ show ip route 203.0.113.1
   Routing entry for 203.0.113.1/32
     Known via "kernel", distance 0, metric 10, best
     Last update 00:00:39 ago
     Flags: Selected
     Status: Installed
     * 192.0.2.1, via eth0, weight 1

Two failover routes with different metrics
==========================================

The following example configures two failover routes to ``203.0.113.1/32``,
each through a different next-hop. The primary next-hop ``192.0.2.1`` is
reached on ``eth0`` with metric 10, and the backup next-hop ``198.51.100.1``
is reached on ``eth2`` with metric 20. Both next-hops are monitored with ICMP
probes every 5 seconds.

While both health checks succeed, the lower-metric route through ``eth0`` is
preferred. If the primary target stops responding, its route is removed from
the routing table, and traffic falls over to ``198.51.100.1`` via ``eth2``.

.. code-block:: none

   set protocols failover route 203.0.113.1/32 next-hop 192.0.2.1 check target '192.0.2.1'
   set protocols failover route 203.0.113.1/32 next-hop 192.0.2.1 check timeout '5'
   set protocols failover route 203.0.113.1/32 next-hop 192.0.2.1 check type 'icmp'
   set protocols failover route 203.0.113.1/32 next-hop 192.0.2.1 interface 'eth0'
   set protocols failover route 203.0.113.1/32 next-hop 192.0.2.1 metric '10'

   set protocols failover route 203.0.113.1/32 next-hop 198.51.100.1 check target '198.51.100.99'
   set protocols failover route 203.0.113.1/32 next-hop 198.51.100.1 check timeout '5'
   set protocols failover route 203.0.113.1/32 next-hop 198.51.100.1 check type 'icmp'
   set protocols failover route 203.0.113.1/32 next-hop 198.51.100.1 interface 'eth2'
   set protocols failover route 203.0.113.1/32 next-hop 198.51.100.1 metric '20'

Verify routes:

.. code-block:: none

   vyos@vyos:~$ show ip route 203.0.113.1
   Routing entry for 203.0.113.1/32
     Known via "kernel", distance 0, metric 10, best
     Last update 00:08:06 ago
     Flags: Selected
     Status: Installed
     * 192.0.2.1, via eth0, weight 1

   Routing entry for 203.0.113.1/32
     Known via "kernel", distance 0, metric 20
     Last update 00:08:14 ago
     Flags: None
     Status: Installed
     * 198.51.100.1, via eth2, weight 1