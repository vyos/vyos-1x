.. _openfabric:

##########
OpenFabric
##########

OpenFabric, specified in `draft-white-openfabric-06.txt
<https://datatracker.ietf.org/doc/html/draft-white-openfabric-06>`_, is
a routing protocol derived from IS-IS, providing link-state routing with
efficient flooding for topologies like spine-leaf networks.

OpenFabric a dual stack protocol.
A single OpenFabric instance is able to perform routing for both IPv4 and IPv6.

*******
General
*******

Configuration
=============

Mandatory Settings
------------------

For OpenFabric to operate correctly, one must do the equivalent of a Router ID
in Connectionless Network Service (CLNS). This Router ID is called the
:abbr:`NET (Network Entity Title)`. The system identifier must be unique within
the network

.. cfgcmd:: set protocols openfabric net <network-entity-title>

  This command sets network entity title (NET) provided in ISO format.

  Here is an example :abbr:`NET (Network Entity Title)` value:

  .. code-block:: none

    49.0001.1921.6800.1002.00

  The CLNS address consists of the following parts:

  * :abbr:`AFI (Address family authority identifier)` - ``49`` The AFI value
    49 is what OpenFabric uses for private addressing.

  * Area identifier: ``0001`` OpenFabric area number (numerical area ``1``)

  * System identifier: ``1921.6800.1002`` - for system identifiers we recommend
    to use IP address or MAC address of the router itself. The way to construct
    this is to keep all of the zeroes of the router IP address, and then change
    the periods from being every three numbers to every four numbers. The
    address that is listed here is ``192.168.1.2``, which if expanded will turn
    into ``192.168.001.002``. Then all one has to do is move the dots to have
    four numbers instead of three. This gives us ``1921.6800.1002``.

  * :abbr:`NET (Network Entity Title)` selector: ``00`` Must always be 00. This
    setting indicates "this system" or "local system."

.. cfgcmd:: set protocols openfabric domain <name> interface <interface>
   address-family <ipv4|ipv6>

  This command enables OpenFabric instance with <NAME> on this interface, and
  allows for adjacency to occur for address family (IPv4 or IPv6 or both).

OpenFabric Global Configuration
-------------------------------

.. cfgcmd:: set protocols openfabric domain-password <plaintext-password|md5>
  <password>

  This command configures the authentication password for a routing domain,
  as clear text or md5 one.

.. cfgcmd:: set protocols openfabric domain <name> purge-originator

  This command enables :rfc:`6232` purge originator identification.

.. cfgcmd:: set protocols openfabric domain <name> set-overload-bit

  This command sets overload bit to avoid any transit traffic through this
  router.

.. cfgcmd:: set protocols openfabric domain <name> log-adjacency-changes

  Log changes in adjacency state.

.. cfgcmd:: set protocols openfabric domain <name> fabric-tier <number>

  This command sets a static tier number to advertise as location
  in the fabric.


Interface Configuration
-----------------------

.. cfgcmd:: set protocols openfabric interface <interface> hello-interval
  <seconds>

  This command sets hello interval in seconds on a given interface.
  The range is 1 to 600. Hello packets are used to establish and maintain
  adjacency between OpenFabric neighbors.

.. cfgcmd:: set protocols openfabric domain <name> interface <interface>
   hello-multiplier <number>

  This command sets multiplier for hello holding time on a given
  interface. The range is 2 to 100.

.. cfgcmd:: set protocols openfabric domain <name> interface <interface>
   metric <metric>

  This command sets default metric for circuit.
  The metric range is 1 to 16777215.

.. cfgcmd:: set protocols openfabric interface <interface> passive

  This command enables the passive mode for this interface.

.. cfgcmd:: set protocols openfabric domain <name> interface <interface>
   password plaintext-password <text>

  This command sets the authentication password for the interface.

.. cfgcmd:: set protocols openfabric domain <name> interface <interface>
   csnp-interval <seconds>

  This command sets Complete Sequence Number Packets (CSNP) interval in seconds.
  The interval range is 1 to 600.

.. cfgcmd:: set protocols openfabric domain <name> interface <interface>
   psnp-interval <number>

  This command sets Partial Sequence Number Packets (PSNP) interval in seconds.
  The interval range is 1 to 120.

Timers
------

.. cfgcmd:: set protocols openfabric domain <name> lsp-gen-interval <seconds>

  This command sets minimum interval at which link-state packets (LSPs) are
  generated. The interval range is 1 to 120.

.. cfgcmd:: set protocols openfabric domain <name> lsp-refresh-interval <seconds>

  This command sets LSP refresh interval in seconds. The interval range
  is 1 to 65235.

.. cfgcmd:: set protocols openfabric domain <name> max-lsp-lifetime <seconds>

  This command sets LSP maximum LSP lifetime in seconds. The interval range
  is 360 to 65535. LSPs remain in a database for 1200 seconds by default.
  If they are not refreshed by that time, they are deleted. You can change
  the LSP refresh interval or the LSP lifetime. The LSP refresh interval
  should be less than the LSP lifetime or else LSPs will time out before
  they are refreshed.

.. cfgcmd:: set protocols openfabric domain <name> spf-interval <seconds>

  This command sets minimum interval between consecutive shortest path first
  (SPF) calculations in seconds.The interval range is 1 to 120.


********
Examples
********

Enable OpenFabric
=================

**Node 1:**

.. code-block:: none

  set interfaces loopback lo address '192.168.255.255/32'
  set interfaces ethernet eth1 address '192.0.2.1/24'

  set protocols openfabric domain VyOS interface eth1 address-family ipv4
  set protocols openfabric domain VyOS interface lo address-family ipv4
  set protocols openfabric net '49.0001.1921.6825.5255.00'

**Node 2:**

.. code-block:: none

  set interfaces loopback lo address '192.168.255.254/32'
  set interfaces ethernet eth1 address '192.0.2.2/24'

  set protocols openfabric domain VyOS interface eth1 address-family ipv4
  set protocols openfabric domain VyOS interface lo address-family ipv4
  set protocols openfabric net '49.0001.1921.6825.5254.00'



This gives us the following neighborships:

.. code-block:: none

  Node-1@vyos:~$ show openfabric neighbor
  show openfabric neighbor
  Area VyOS:
    System Id           Interface   L  State        Holdtime SNPA
   vyos                eth1        2  Up            27       2020.2020.2020


  Node-2@vyos:~$ show openfabric neighbor
  show openfabric neighbor
  Area VyOS:
    System Id           Interface   L  State        Holdtime SNPA
   vyos                eth1        2  Up            30       2020.2020.2020

Here's the IP routes that are populated:

.. code-block:: none

  Node-1@vyos:~$ show ip route openfabric
  show ip route openfabric
  Codes: K - kernel route, C - connected, S - static, R - RIP,
         O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
         T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
         f - OpenFabric,
         > - selected route, * - FIB route, q - queued, r - rejected, b - backup
         t - trapped, o - offload failure

  f   192.0.2.0/24 [115/20] via 192.0.2.2, eth1 onlink, weight 1, 00:00:10
  f>* 192.168.255.254/32 [115/20] via 192.0.2.2, eth1 onlink, weight 1, 00:00:10

  Node-2@vyos:~$ show ip route openfabric
  show ip route openfabric
  Codes: K - kernel route, C - connected, S - static, R - RIP,
         O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
         T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
         f - OpenFabric,
         > - selected route, * - FIB route, q - queued, r - rejected, b - backup
         t - trapped, o - offload failure

  f   192.0.2.0/24 [115/20] via 192.0.2.1, eth1 onlink, weight 1, 00:00:48
  f>* 192.168.255.255/32 [115/20] via 192.0.2.1, eth1 onlink, weight 1, 00:00:48
