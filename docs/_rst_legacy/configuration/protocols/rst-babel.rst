.. _babel:
.. meta::
   :description: The Babel routing protocol provides robust and efficient 
                 routing for wired and wireless mesh networks.
   :keywords: babel, routing, protocol, wireless, mesh, network, metric, 
              ipv4, ipv6

#####
Babel
#####

The Babel protocol provides robust and efficient routing for both wired and 
wireless mesh networks. By default, Babel uses hop-count metrics on wired links 
and a variant of Expected Transmission Count (ETX) on wireless links. 
Administrators can configure Babel to account for radio diversity, 
automatically compute link latency, and include that latency in the routing 
metric. :rfc:`8966` defines the Babel protocol.

Babel is a dual-stack protocol. A single Babel instance routes both IPv4 and 
IPv6 traffic simultaneously.

General configuration
---------------------

VyOS does not require a specific command to start the Babel process. The system 
automatically starts the routing process when you configure the first 
Babel-enabled interface.

.. cfgcmd:: set protocols babel interface <interface>

   **Enable Babel routing on the specified interface.**

   The system immediately begins sending and receiving Babel packets on this 
   interface.

Optional configuration
----------------------

.. cfgcmd:: set protocols babel parameters diversity

   **Enable radio-frequency diversity routing for the Babel process.**

   Enabling this feature is highly recommended for networks with many 
   wireless nodes.

   .. note:: When you enable diversity routing, you should also configure the 
      ``diversity-factor`` and ``channel`` parameters.

.. cfgcmd:: set protocols babel parameters diversity-factor <1-256>

   **Configure the multiplicative factor for diversity routing, in units of 
   1/256.**

   Lower multiplicative factors give greater weight to diversity in route 
   selection. The default value is 256, which disables diversity routing. 
   On nodes with multiple independent radios, configure a value of 128 or less.

.. cfgcmd:: set protocols babel parameters resend-delay <20-655340>

   **Configure the delay in milliseconds before the system resends an 
   important request or update.**

   The default value is 2000 ms.

.. cfgcmd:: set protocols babel parameters smoothing-half-life <0-65534>

   **Configure the time constant, in seconds, for the smoothing algorithm used 
   to implement hysteresis.**

   Higher values reduce route oscillation but slightly increase convergence 
   time. A value of 0 disables hysteresis and is suitable for wired networks. 
   The default is 4 seconds.

Interfaces configuration
------------------------

.. cfgcmd:: set protocols babel interface <interface> type <auto|wired|wireless>

   **Configure the network type for the Babel-enabled interface.**

   Choose from the following:

   * ``auto``: Babel automatically detects if an interface is wired or 
     wireless.
   * ``wired``: Babel enables optimizations for wired interfaces.
   * ``wireless``: Babel disables optimizations suitable only for wired 
     interfaces. Specifying wireless is always correct, but may cause slower 
     convergence and increased routing traffic.

.. cfgcmd:: set protocols babel interface <interface> split-horizon <default|disable|enable>

   **Configure the split-horizon routing behavior for the specified 
   interface.**

   Use one of the following options:

   * ``default``: Babel automatically enables split-horizon on wired 
     interfaces and disables it on wireless interfaces.
   * ``enable``: Babel enables split-horizon on the interface. This 
     optimization should be used only on symmetric, transitive (wired) 
     networks.
   * ``disable``: Babel disables split-horizon on the interface. Disabling 
     split-horizon is always safe and correct.

.. cfgcmd:: set protocols babel interface <interface> hello-interval <20-655340>

   **Configure the interval, in milliseconds, between scheduled hello messages 
   on the specified interface.**

   On wired links, Babel detects link failures within two hello intervals. 
   On wireless links, link quality is reestimated at each interval. The 
   default is 4000 ms.

.. cfgcmd:: set protocols babel interface <interface> update-interval <20-655340>

   **Configure the interval, in milliseconds, between scheduled routing 
   updates on the specified interface.**

   Because Babel uses triggered updates extensively, you can increase this 
   value on reliable links with minimal packet loss. The default is 20000 ms.

.. cfgcmd:: set protocols babel interface <interface> rxcost <1-65534>

   **Configure the base receive cost for the specified interface.**

   Babel applies this value based on the configured network type:

   * ``wired``: The value is the routing cost advertised to neighboring 
     routers.
   * ``wireless``: The value is a multiplier used to compute the ETX 
     (Expected Transmission Count) reception cost.

   The default value is 256.

.. cfgcmd:: set protocols babel interface <interface> rtt-decay <1-256>

   **Configure the decay factor for the exponential moving average of RTT 
   samples, in units of 1/256.**

   Higher values discard older samples faster. The default value is 42.

.. cfgcmd:: set protocols babel interface <interface> rtt-min <1-65535>

   **Configure the minimum RTT, in milliseconds, at which the cost to a 
   neighbor begins to increase.**

   The additional cost is linear in (rtt - rtt-min). The default value is 10 ms.

.. cfgcmd:: set protocols babel interface <interface> rtt-max <1-65535>

   **Configure the maximum RTT, in milliseconds, above which the cost to a 
   neighbor stops increasing.**

   The default value is 120 ms.

.. cfgcmd:: set protocols babel interface <interface> max-rtt-penalty <0-65535>

   **Configure the maximum cost added to a neighbor when RTT meets or exceeds 
   rtt-max.**

   Setting this value to 0 disables RTT-based costs. The default value is 150.

.. cfgcmd:: set protocols babel interface <interface> enable-timestamps

   **Configure adding timestamps to each Hello and IHU message to calculate 
   RTT values.**

   Enabling timestamps is recommended for tunnel interfaces.

.. cfgcmd:: set protocols babel interface <interface> channel <1-254|interfering|noninterfering>

   **Configure the channel identifier that diversity routing uses for the 
   specified interface.**

   Interfaces interfere with each other based on the assigned channel 
   identifier:

   * ``1–254``: The interface interferes with interfaces sharing the same 
     channel number and with interfaces configured as ``interfering``.
   * ``interfering``: The interface interferes with all others except those 
     configured as ``noninterfering``.
   * ``noninterfering``: The interface interferes only with itself.

Redistribution configuration
----------------------------

.. cfgcmd:: set protocols babel redistribute <ipv4|ipv6> <route source>

   **Configure the redistribution of routing information from the specified 
   route source into the Babel process.**

   The following route sources are available:

   * **ipv4:** ``bgp``, ``connected``, ``eigrp``, ``isis``, ``kernel``, 
     ``nhrp``, ``ospf``, ``rip``, ``static``
   * **ipv6:** ``bgp``, ``connected``, ``eigrp``, ``isis``, ``kernel``, 
     ``nhrp``, ``ospfv3``, ``ripng``, ``static``

.. cfgcmd:: set protocols babel distribute-list <ipv4|ipv6> access-list <in|out> <number>

   **Configure global Babel route filtering using an access list.**

   Specify the direction in which the access list is applied:

   * ``in``: Filters incoming routes.
   * ``out``: Filters outgoing routes.

.. cfgcmd:: set protocols babel distribute-list <ipv4|ipv6> interface <interface> access-list <in|out> <number>

   **Configure Babel route filtering on the specified interface using an 
   access list.**

   Specify the direction in which the access list is applied:

   * ``in``: Filters incoming routes.
   * ``out``: Filters outgoing routes.

.. cfgcmd:: set protocols babel distribute-list <ipv4|ipv6> prefix-list <in|out> <name>

   **Configure global Babel route filtering using a prefix list.**

   Specify the direction in which the prefix list is applied:

   * ``in``: Filters incoming routes.
   * ``out``: Filters outgoing routes.

.. cfgcmd:: set protocols babel distribute-list <ipv4|ipv6> interface <interface> prefix-list <in|out> <name>

   **Configure Babel route filtering on the specified interface using a 
   prefix list.**

   Specify the direction in which the prefix list is applied:

   * ``in``: Filters incoming routes.
   * ``out``: Filters outgoing routes.

Configuration example
---------------------

Basic two-node babel network
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Goal:** The following example connects two routers (Node 1 and Node 2) via 
their eth0 interfaces and uses the Babel routing protocol to advertise 
(redistribute) each router's locally configured networks (represented by 
loopback addresses) to one another.

**Node 1:**

.. code-block:: none

   # Configure the loopback (local networks) and physical (eth0) addresses
   set interfaces loopback lo address 10.1.1.1/32
   set interfaces loopback lo address fd12:3456:dead:beef::1/128
   set interfaces ethernet eth0 address 192.168.1.1/24

   # Enable Babel on the physical link
   set protocols babel interface eth0 type wired

   # Instruct Babel to advertise (redistribute) the locally configured networks
   set protocols babel redistribute ipv4 connected
   set protocols babel redistribute ipv6 connected

**Node 2:**

.. code-block:: none

   # Configure the loopback (local networks) and physical (eth0) addresses
   set interfaces loopback lo address 10.2.2.2/32
   set interfaces loopback lo address fd12:3456:beef:dead::2/128
   set interfaces ethernet eth0 address 192.168.1.2/24

   # Enable Babel on the physical link
   set protocols babel interface eth0 type wired

   # Tell Babel to advertise (redistribute) the locally configured networks
   set protocols babel redistribute ipv4 connected
   set protocols babel redistribute ipv6 connected
