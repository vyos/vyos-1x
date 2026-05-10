:lastproofread: 2026-03-03

.. _pppoe-interface:

#####
PPPoE
#####

:abbr:`PPPoE (Point-to-Point Protocol over Ethernet)` is a network protocol 
that encapsulates PPP frames within Ethernet frames.
It's often used for connecting ISP clients to a broadband access server.

*************
Configuration
*************

Common interface configuration
==============================

.. cmdinclude:: /_include/interface-description.txt
   :var0: pppoe
   :var1: pppoe0

.. cmdinclude:: /_include/interface-disable.txt
   :var0: pppoe
   :var1: pppoe0

.. cmdinclude:: /_include/interface-mtu.txt
   :var0: pppoe
   :var1: pppoe0

.. cmdinclude:: /_include/interface-vrf.txt
   :var0: pppoe
   :var1: pppoe0

PPPoE options
=============

.. cfgcmd:: set interfaces pppoe <interface> access-concentrator <name>

   **Configure the name of the target access concentrator for the PPPoE session.**

   During the PPPoE discovery process, the client sends a PPPoE initiation packet. 
   Multiple access concentrators may respond with offer packets, and the client 
   selects one of them.

   This setting restricts the client to establishing sessions only with the 
   specified access concentrator.

.. cfgcmd:: set interfaces pppoe <interface> authentication username <username>

   **Configure the username for PPPoE session authentication.**

   Although authentication is optional in the interface configuration, most ISPs 
   require it to establish a connection.

.. cfgcmd:: set interfaces pppoe <interface> authentication password <password>

   **Configure the password for PPPoE session authentication.**

   Although authentication is optional in the interface configuration, most ISPs 
   require it to establish a connection.

.. cfgcmd:: set interfaces pppoe <interface> connect-on-demand

   **Enable dial-on-demand on the PPPoE interface.**

   When enabled, the system establishes a PPPoE connection only when traffic 
   passes through the interface. If the connection fails, it is reestablished when 
   traffic resumes.

   For on-demand connections, you must also configure an ``idle-timeout`` period 
   to disconnect the session after inactivity. 

   .. note:: Setting the idle timeout to zero, or leaving it unconfigured, keeps 
      the connection active continuously once established.

   By default, the PPPoE connection is established at boot and remains active 
   continuously; if the connection fails, it is reestablished immediately.

.. cfgcmd:: set interfaces pppoe <interface> no-default-route

   Request an IP address from the PPPoE server without installing a default route.

   Example:

   .. code-block:: none

     set interfaces pppoe pppoe0 no-default-route

   .. note:: Introduced in VyOS 1.4, this command inverts the logic of the former 
      ``default-route`` CLI option.

.. cfgcmd:: set interfaces pppoe <interface> default-route-distance <distance>

   Configure the distance for the default gateway provided by the PPPoE server.

   Example:

   .. code-block:: none

     set interfaces pppoe pppoe0 default-route-distance 220

.. cfgcmd:: set interfaces pppoe <interface> mru <mru>

   **Configure the** :abbr:`MRU (Maximum Receive Unit)` **for the PPPoE 
   interface.**

   This setting instructs the pppd daemon to restrict the remote peer from sending 
   packets larger than the configured MRU. Allowed MRU values range from 128 to 
   16384 bytes.

   An MRU of 296 is suitable for very slow links (40 bytes for the TCP/IP header 
   and 256 bytes for data).

   The default MRU is 1492 bytes.

   .. note:: When using the IPv6 protocol, the MRU must be at least 1280 bytes.

.. cfgcmd:: set interfaces pppoe <interface> idle-timeout <time>

   **Configure the idle timeout for on-demand PPPoE sessions.**

   This setting defines how long the connection remains active without any traffic 
   before being disconnected. 

   .. note:: Setting the idle timeout to zero, or leaving it unconfigured, keeps 
      the connection active continuously once established.

.. cfgcmd:: set interfaces pppoe <interface> holdoff <time>

   **Configure the redial delay for persistent PPPoE sessions.**

   If a persistent session (with ``connect-on-demand`` disabled) is terminated by 
   the remote peer or drops unexpectedly, the router waits the specified interval 
   before attempting to reconnect.

   The default redial delay is 30 seconds.

.. cfgcmd:: set interfaces pppoe <interface> local-address <address>

   **Configure the local endpoint IP address for PPPoE sessions.**

   By default, this IP address is negotiated.

.. cfgcmd:: set interfaces pppoe <interface> no-peer-dns

   Disable the installation of advertised DNS nameservers on the local system.

.. cfgcmd:: set interfaces pppoe <interface> remote-address <address>

   **Configure the remote endpoint IP address for PPPoE sessions.**

   By default, this IP address is negotiated.

.. cfgcmd:: set interfaces pppoe <interface> service-name <name>

   **Configure the service name of the target access concentrator for the PPPoE 
   session.**

   By default, the PPPoE interface connects to any available access concentrator.

.. cfgcmd:: set interfaces pppoe <interface> source-interface <source-interface>

   **Configure the underlying interface for the PPPoE connection.**

   Each PPPoE connection is established over an underlying interface, which can be 
   an Ethernet interface, a VIF, or a bonding interface. 

.. cfgcmd:: set interfaces pppoe <interface> ip adjust-mss <mss | clamp-mss-to-pmtu>

  **Configure the** :abbr:`MSS (Maximum Segment Size)` **advertised in outgoing 
  TCP SYN packets on the specified interface.**

  By clamping the MSS value in TCP SYN packets, you instruct the remote side not 
  to send packets larger than the specified size. This helps prevent connection 
  issues if :abbr:`PMTUD (Path MTU Discovery)` fails.

  The following options are available:

  * ``mss``: Sets the MSS to a specific value in bytes.
  * ``clamp-mss-to-pmtu``: Sets the MSS to the interface’s MTU minus 40 bytes for 
    IPv4 traffic (20 bytes for the IPv4 header and 20 bytes for the TCP header). 
    This option is recommended to automatically set the proper value.

  .. note:: Introduced in VyOS 1.4, this command replaces the older ``set firewall 
     options interface <name> adjust-mss <value>`` syntax.

.. cfgcmd:: set interfaces pppoe <interface> ip disable-forwarding

  **Configure the interface for host or router behavior.**

  If configured, the interface switches to host mode, and IPv4 forwarding is 
  disabled on it.

.. cfgcmd:: set interfaces pppoe <interface> ip source-validation <strict | loose | disable>

  **Configure source IP address validation using** 
  :abbr:`RPF (Reverse Path Forwarding)` **on this interface, as specified in** 
  :rfc:`3704`.

  The following options are available:

  * ``strict``: Each incoming packet’s source IP address is checked against the 
    :abbr:`FIB (Forwarding Information Base)`. If the interface is not the best 
    route back to that source, validation fails, and the packet is dropped.
  * ``loose``: Each incoming packet’s source IP address is checked against the 
    :abbr:`FIB (Forwarding Information Base)`. If the source IP address is 
    unreachable through any interface, validation fails.
  * ``disable``: No source IP address validation is performed. All incoming 
    packets are accepted.

  :rfc:`3704` recommends enabling ``strict`` mode to prevent IP spoofing, such as 
  DDoS attacks. For asymmetric or other complex routing scenarios, use ``loose`` 
  mode.

IPv6
----

.. cfgcmd:: set interfaces pppoe <interface> ipv6 address autoconf

   Enable IPv6 address assignment via :abbr:`SLAAC (Stateless Address 
   Auto-Configuration)` on this interface.

.. cfgcmd:: set interfaces pppoe <interface> ipv6 adjust-mss <mss | clamp-mss-to-pmtu>

  **Configure the** :abbr:`MSS (Maximum Segment Size)` **advertised in outgoing 
  TCP SYN packets on the specified interface.**

  By clamping the MSS value in TCP SYN packets, you instruct the remote side not 
  to send packets larger than the specified size. This helps prevent connection 
  issues if :abbr:`PMTUD (Path MTU Discovery)` fails.

  The following options are available:

  * ``mss``: Sets the MSS to a specific value in bytes.
  * ``clamp-mss-to-pmtu``: Sets the MSS to the interface’s MTU minus 60 bytes for 
    IPv6 traffic (40 bytes for the IPv6 header and 20 bytes for the TCP header). 
    This option is recommended to automatically set the proper value.

  .. note:: Introduced in VyOS 1.4, this command replaces the older ``set firewall 
     options interface <name> adjust-mss <value>`` syntax.


.. cfgcmd:: set interfaces pppoe <interface> ipv6 disable-forwarding

  **Configure the interface for host or router behavior.**

  If configured, the interface switches to host mode, and IPv6 forwarding is
  disabled on it.

.. cmdinclude:: /_include/interface-dhcpv6-prefix-delegation.txt
  :var0: pppoe
  :var1: pppoe0

*********
Operation
*********

.. opcmd:: show interfaces pppoe <interface>

   Show detailed information about a specific PPPoE interface.

   .. code-block:: none

     vyos@vyos:~$ show interfaces pppoe pppoe0
     pppoe0: <POINTOPOINT,MULTICAST,NOARP,UP,LOWER_UP> mtu 1492 qdisc pfifo_fast state UNKNOWN group default qlen 3
         link/ppp
         inet 192.0.2.1 peer 192.0.2.255/32 scope global pppoe0
            valid_lft forever preferred_lft forever

         RX:  bytes    packets     errors    dropped    overrun      mcast
         7002658233    5064967          0          0          0          0
         TX:  bytes    packets     errors    dropped    carrier collisions
          533822843    1620173          0          0          0          0

.. opcmd:: show interfaces pppoe <interface> queue

   Show queue information for a specific PPPoE interface.

   .. code-block:: none

     vyos@vyos:~$ show interfaces pppoe pppoe0 queue
     qdisc pfifo_fast 0: root refcnt 2 bands 3 priomap  1 2 2 2 1 2 0 0 1 1 1 1 1 1 1 1
      Sent 534625359 bytes 1626761 pkt (dropped 62, overlimits 0 requeues 0)
      backlog 0b 0p requeues 0

Connect/disconnect
==================

.. opcmd:: disconnect interface <interface>

   Disconnect the specified interface. 

.. opcmd:: connect interface <interface>

   Initiate a session on the specified interface.

*******
Example
*******

PPPoE over DSL
============== 

**Configuration scenario:**

* Your ISP's DSL modem is connected to the ``eth0`` interface on your VyOS 
  router.
* Your ISP does not require VLAN tagging.
* PPPoE credentials are provided by your ISP. The typical username format is 
  ``name@host.net``, though this may vary.

**Configuration notes:**

* The maximum MTU size for DSL is 1492 because of PPPoE overhead. If you are 
  switching from a DHCP-based ISP (e.g., a standard cable connection), ensure 
  VPN links have MTU sizes adjusted accordingly.
* To ignore ISP-provided nameservers and use only your statically configured 
  ones, set the ``name-server`` option to ``none``.
* A default route is automatically installed once the interface is up. To 
  change this behavior, use the ``no-default-route`` CLI option.

.. note:: The PPPoE configuration syntax changed after VyOS 1.2 (Crux) and is 
   automatically migrated during an upgrade.


.. code-block:: none

  set interfaces pppoe pppoe0 authentication username 'userid'
  set interfaces pppoe pppoe0 authentication password 'secret'
  set interfaces pppoe pppoe0 source-interface 'eth0'


Secure your setup by creating rules matching the ``pppoe0`` interface in the 
firewall chains:

.. code-block:: none

  set firewall ipv4 input filter rule 10 inbound-interface name 'pppoe0'
  set firewall ipv4 forward filter rule 10 inbound-interface name 'pppoe0'
 

PPPoE over VLAN 
===============

Some ISPs require PPPoE connections to be 
established over a VLAN interface. This specific topology is fully supported by 
VyOS.

The following configuration establishes the PPPoE connection through VLAN 7, 
which is the default VLAN for Deutsche Telekom:

.. code-block:: none

  set interfaces pppoe pppoe0 authentication username 'userid'
  set interfaces pppoe pppoe0 authentication password 'secret'
  set interfaces pppoe pppoe0 source-interface 'eth0.7'


IPv6 DHCPv6 prefix delegation
-----------------------------

.. stop_vyoslinter

**Configuration scenario:**

The following configuration establishes a PPPoE session on the ``eth1`` 
interface, requests a ``/56`` IPv6 prefix delegation from the ISP, and assigns 
a ``/64`` subnet from that delegation to the ``eth0`` interface.

**Configuration notes:**

* The IPv6 address assigned to ``eth0`` is ``<prefix>::1/64``.
* If you do not know your delegated prefix size, begin with ``sla-len 0``.
* To advertise the prefix on the ``eth0`` link, configure IPv6 Router 
  Advertisement.

.. start_vyoslinter

.. code-block:: none

  set interfaces pppoe pppoe0 authentication username vyos
  set interfaces pppoe pppoe0 authentication password vyos
  set interfaces pppoe pppoe0 dhcpv6-options pd 0 interface eth0 address '1'
  set interfaces pppoe pppoe0 dhcpv6-options pd 0 interface eth0 sla-id '0'
  set interfaces pppoe pppoe0 dhcpv6-options pd 0 length '56'
  set interfaces pppoe pppoe0 ipv6 address autoconf
  set interfaces pppoe pppoe0 source-interface eth1

  set service router-advert interface eth0 prefix ::/64
