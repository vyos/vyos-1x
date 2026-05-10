:lastproofread: 2026-03-16

.. _sstp-client-interface:

###########
SSTP client
###########

:abbr:`SSTP (Secure Socket Tunneling Protocol)` transports PPP traffic over an 
SSL/TLS channel, providing transport-level security through key negotiation, 
encryption, and traffic integrity checking. The use of SSL/TLS over TCP port 
443 (by default, the port can be changed) allows SSTP to pass through virtually 
all firewalls and proxy servers, except for authenticated web proxies.

.. note:: VyOS includes a built-in SSTP server. For more information, see 
   :ref:`sstp`.

*************
Configuration
*************

Common interface configuration
==============================

.. cmdinclude:: /_include/interface-description.txt
   :var0: sstpc
   :var1: sstpc0

.. cmdinclude:: /_include/interface-disable.txt
   :var0: sstpc
   :var1: sstpc0

.. cmdinclude:: /_include/interface-mtu.txt
   :var0: sstpc
   :var1: sstpc0

.. cmdinclude:: /_include/interface-vrf.txt
   :var0: sstpc
   :var1: sstpc0

SSTP client options
===================

.. cfgcmd:: set interfaces sstpc <interface> no-default-route

   Request an IP address from the SSTP server without installing a default route.

   Example:

   .. code-block:: none

     set interfaces sstpc sstpc0 no-default-route

   .. note:: Introduced in VyOS 1.4, this command inverts the logic of the former 
      ``default-route`` CLI option.

.. cfgcmd:: set interfaces sstpc <interface> default-route-distance <distance>

   Configure the distance for the default gateway provided by the SSTP server.

   Example:

   .. code-block:: none

     set interfaces sstpc sstpc0 default-route-distance 220

.. cfgcmd:: set interfaces sstpc <interface> no-peer-dns

   Disable the installation of advertised DNS nameservers on the local system.

.. cfgcmd:: set interfaces sstpc <interface> server <address>

   **Configure the remote SSTP server address for the client connection.**

   The address can be either an IP address or a :abbr:`FQDN (Fully Qualified 
   Domain Name)`.

.. cfgcmd:: set interfaces sstpc <interface> ip adjust-mss <mss | clamp-mss-to-pmtu>

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

.. cfgcmd:: set interfaces sstpc <interface> ip disable-forwarding

  **Configure the interface for host or router behavior.**

  If configured, the interface switches to host mode, and IPv4 forwarding is 
  disabled on it.

.. cfgcmd:: set interfaces sstpc <interface> ip source-validation <strict | loose | disable>

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

*********
Operation
*********

.. opcmd:: show interfaces sstpc <interface>

  Show detailed information about the specified interface.

   .. code-block:: none

     vyos@vyos:~$ show interfaces sstpc sstpc10
     sstpc10: <POINTOPOINT,MULTICAST,NOARP,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UNKNOWN group default qlen 3
         link/ppp
         inet 192.0.2.5 peer 192.0.2.254/32 scope global sstpc10
            valid_lft forever preferred_lft forever
         inet6 fe80::fd53:c7ff:fe8b:144f/64 scope link
            valid_lft forever preferred_lft forever

         RX:  bytes  packets  errors  dropped  overrun       mcast
                215        9       0        0        0           0
         TX:  bytes  packets  errors  dropped  carrier  collisions
                539       14       0        0        0           0


Connect/disconnect
==================

.. opcmd:: disconnect interface <interface>

   Disconnect the specified interface.

.. opcmd:: connect interface <interface>

   Initiate a session on the specified interface.
