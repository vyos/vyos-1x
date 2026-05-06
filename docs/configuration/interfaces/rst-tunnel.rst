:lastproofread: 2026-01-23

.. _tunnel-interface:

######
Tunnel
######

Tunnel interfaces are virtual links that transmit encapsulated traffic between 
private networks or hosts across public infrastructure, such as the Internet. 
They operate using encapsulation protocols to wrap original traffic for 
transport. The supported protocols include :abbr:`GRE (Generic Routing 
Encapsulation)`, IPIP, IPIP6, IP6IP6, and 6in4 (SIT). 

While :abbr:`GRE (Generic Routing Encapsulation)` is often the preferred 
one-size-fits-all solution due to its versatility, other encapsulation 
protocols may be better suited for specific use cases. 

VyOS uses a single tunnel interface type for all of these protocols. There are 
no separate :abbr:`GRE (Generic Routing Encapsulation)`, IPIP, or IP6IP6 
interface types; instead, the desired encapsulation protocol is selected within 
the ``set interfaces tunnel`` configuration.

Configuration options for each protocol are described below.

.. warning:: Do not change the encapsulation type for already configured tunnel 
   interfaces, as this may break their dependent configurations.

Common interface configuration
------------------------------

.. cmdinclude:: /_include/interface-address.txt
   :var0: tunnel
   :var1: tun0

.. cmdinclude:: /_include/interface-common-without-mac.txt
   :var0: tunnel
   :var1: tun0

IPIP
----

IPIP is a straightforward encapsulation protocol defined in RFC 2003. It 
encapsulates one IPv4 packet inside another IPv4 packet. 

Tunnels with IPIP encapsulation do not have protocol-specific configuration 
options except for explicitly defining the encapsulation type as IPIP (see 
the example below).

Example:

.. code-block:: none

  set interfaces tunnel tun0 encapsulation ipip
  set interfaces tunnel tun0 source-address 192.0.2.10
  set interfaces tunnel tun0 remote 203.0.113.20
  set interfaces tunnel tun0 address 192.168.100.200/24

IP6IP6
------

IP6IP6 is the IPv6 counterpart to IPIP. It encapsulates one IPv6 packet inside 
another IPv6 packet.

Similar to their IPIP counterparts, tunnels with IP6IP6 encapsulation do not 
have protocol-specific configuration options except for explicitly defining 
the encapsulation type as IP6IP6. 

Example:

.. code-block:: none

  set interfaces tunnel tun0 encapsulation ip6ip6
  set interfaces tunnel tun0 source-address 2001:db8:aa::1
  set interfaces tunnel tun0 remote 2001:db8:aa::2
  set interfaces tunnel tun0 address 2001:db8:bb::1/64

IPIP6
-----

IPIP6 is an encapsulation protocol that wraps IPv4 packets inside IPv6 packets.

Similar to IPIP and IP6IP6, protocol-specific configuration for tunnels with 
IPIP6 encapsulation only requires defining the encapsulation type as IP6IP6.

Example:

.. code-block:: none

  set interfaces tunnel tun0 encapsulation ipip6
  set interfaces tunnel tun0 source-address 2001:db8:aa::1
  set interfaces tunnel tun0 remote 2001:db8:aa::2
  set interfaces tunnel tun0 address 192.168.70.80/24

6in4 (SIT)
----------

6in4, also known as :abbr:`SIT (Simple Internet Transition)`, is an 
encapsulation protocol defined in :rfc:`4213` that wraps IPv6 packets 
inside IPv4 packets. The encapsulating IPv4 headers use IP protocol number 41, 
which is reserved exclusively for IPv6 encapsulation.

The encapsulation process adds a 20-byte IPv4 header to each IPv6 packet. 
Consequently, 6in4 tunnel interfaces can transmit IPv6 packets up to 1480 bytes 
over an underlying network with a standard MTU of 1500 bytes without 
fragmentation. 

6in4 tunnel interfaces are frequently used by IPv6 tunnel brokers (such as 
`Hurricane Electric`_) to connect isolated IPv6 networks or individual hosts to 
the IPv6 internet. 

Example:

.. code-block:: none

  set interfaces tunnel tun0 encapsulation sit
  set interfaces tunnel tun0 source-address 192.0.2.10
  set interfaces tunnel tun0 remote 192.0.2.20
  set interfaces tunnel tun0 address 2001:db8:bb::1/64

.. seealso:: For a practical configuration example, see the 
   :ref:`Tunnelbroker.net (IPv6) <examples-tunnelbroker-ipv6>` section.

Generic Routing Encapsulation (GRE)
-----------------------------------

:abbr:`GRE (Generic Routing Encapsulation)` is a versatile encapsulation 
protocol defined in RFC 2784. Unlike simpler protocols such as IPIP, it allows 
both IPv4 and IPv6 to be transported through the same tunnel.

:abbr:`GRE (Generic Routing Encapsulation)` encapsulates original data packets 
by adding a :abbr:`GRE (Generic Routing Encapsulation)` header, followed by an 
IP header (the delivery header). The delivery header uses IP protocol number 47 
to identify :abbr:`GRE (Generic Routing Encapsulation)`-encapsulated traffic.

In VyOS, :abbr:`GRE (Generic Routing Encapsulation)` tunnels can be established 
over both IPv4 (encapsulation ``gre``) and IPv6 (encapsulation ``ip6gre``) 
transport networks.


Configuration
^^^^^^^^^^^^^

To configure a :abbr:`GRE (Generic Routing Encapsulation)` tunnel, you need to 
define a tunnel source IP address, a tunnel destination IP address, an 
encapsulation type (:abbr:`GRE (Generic Routing Encapsulation)`), and a tunnel 
interface IP address.

Example: 

The following example shows how to configure an IPv4/IPv6-over-IPv6 :abbr:`GRE 
(Generic Routing Encapsulation)` tunnel between a VyOS router and a Linux host 
running ``systemd-networkd``.

**VyOS router:**

.. code-block:: none

  set interfaces tunnel tun101 address '2001:db8:feed:beef::1/126'
  set interfaces tunnel tun101 address '192.168.5.1/30'
  set interfaces tunnel tun101 encapsulation 'ip6gre'
  set interfaces tunnel tun101 source-address '2001:db8:babe:face::3afe:3'
  set interfaces tunnel tun101 remote '2001:db8:9bb:3ce::5'

**Linux** ``systemd-networkd``:

The ``systemd-networkd`` setup requires two configuration files: ``xxx.netdev`` 
to create the :abbr:`GRE (Generic Routing Encapsulation)` tunnel interface, and 
``xxx.network`` to assign IP addresses to it.

.. code-block:: none

  # cat /etc/systemd/network/gre-example.netdev
  [NetDev]
  Name=gre-example
  Kind=ip6gre
  MTUBytes=14180

  [Tunnel]
  Remote=2001:db8:babe:face::3afe:3


  # cat /etc/systemd/network/gre-example.network
  [Match]
  Name=gre-example

  [Network]
  Address=2001:db8:feed:beef::2/126

  [Address]
  Address=192.168.5.2/30

GRE keys
^^^^^^^^

A GRE key is an optional 32-bit field in the GRE header that allows multiple 
GRE tunnels to operate between the same source and destination endpoints. When 
a packet arrives, the receiver checks the GRE key to determine which tunnel 
interface should process it.

Although it may sound security-related, the GRE key is only an identifier and 
provides no encryption or data protection.

Example:

.. code-block:: none

   set interfaces tunnel tun0 source-address 192.0.2.10
   set interfaces tunnel tun0 remote 192.0.2.20
   set interfaces tunnel tun0 address 10.40.50.60/24
   set interfaces tunnel tun0 parameters ip key 10

.. code-block:: none

   set interfaces tunnel tun1 source-address 192.0.2.10
   set interfaces tunnel tun1 remote 192.0.2.20
   set interfaces tunnel tun1 address 172.16.17.18/24
   set interfaces tunnel tun1 parameters ip key 20

GRETAP
^^^^^^^

Unlike GRE, which encapsulates only Layer 3 (IP) traffic, GRETAP encapsulates 
Layer 2 (Ethernet) frames.

That means that GRETAP tunnel interfaces can be members of a bridge interface. 
This allows two geographically distant sites to connect as if they were on the 
same LAN.

GRETAP tunnels can be established over both IPv4 and IPv6 transport networks.

Example:

.. code-block:: none

   set interfaces bridge br0 member interface eth0
   set interfaces bridge br0 member interface tun0
   set interfaces tunnel tun0 encapsulation gretap
   set interfaces tunnel tun0 source-address 198.51.100.2
   set interfaces tunnel tun0 remote 203.0.113.10


Troubleshooting
^^^^^^^^^^^^^^^

GRE is a standardized tunneling protocol used in many network environments.

Although the GRE tunnel setup is straightforward, connectivity failures 
frequently occur because ACLs or firewall rules block IP protocol 47 or 
prevent direct communication between the tunnel endpoints.

If your GRE tunnel fails to establish, perform these diagnostic steps:

1. Verify that the remote peer is reachable from the configured 
``source-address``. 

This ensures that the underlying physical path between the two endpoints is 
functional.

.. code-block:: none

  vyos@vyos:~$ ping 203.0.113.10 interface 198.51.100.2 count 4
  PING 203.0.113.10 (203.0.113.10) from 198.51.100.2 : 56(84) bytes of data.
  64 bytes from 203.0.113.10: icmp_seq=1 ttl=254 time=0.807 ms
  64 bytes from 203.0.113.10: icmp_seq=2 ttl=254 time=1.50 ms
  64 bytes from 203.0.113.10: icmp_seq=3 ttl=254 time=0.624 ms
  64 bytes from 203.0.113.10: icmp_seq=4 ttl=254 time=1.41 ms

  --- 203.0.113.10 ping statistics ---
  4 packets transmitted, 4 received, 0% packet loss, time 3007ms
  rtt min/avg/max/mdev = 0.624/1.087/1.509/0.381 ms

2. Verify that the tunnel interface is correctly configured (with the link type 
set to GRE) and is actively processing traffic.

.. code-block:: none

  vyos@vyos:~$ show interfaces tunnel tun100
  tun100@NONE: <POINTOPOINT,NOARP,UP,LOWER_UP> mtu 1476 qdisc noqueue state UNKNOWN group default qlen 1000
    link/gre 198.51.100.2 peer 203.0.113.10
    inet 10.0.0.1/30 brd 10.0.0.3 scope global tun100
       valid_lft forever preferred_lft forever
    inet6 fe80::5efe:c612:2/64 scope link
       valid_lft forever preferred_lft forever

    RX:  bytes    packets     errors    dropped    overrun      mcast
          2183         27          0          0          0          0
    TX:  bytes    packets     errors    dropped    carrier collisions
           836          9          0          0          0          0

3. Test the connection through the tunnel using the private IP addresses 
assigned to each tunnel endpoint.

.. code-block:: none

  vyos@vyos:~$ ping 10.0.0.2 interface 10.0.0.1 count 4
  PING 10.0.0.2 (10.0.0.2) from 10.0.0.1 : 56(84) bytes of data.
  64 bytes from 10.0.0.2: icmp_seq=1 ttl=255 time=1.05 ms
  64 bytes from 10.0.0.2: icmp_seq=2 ttl=255 time=1.88 ms
  64 bytes from 10.0.0.2: icmp_seq=3 ttl=255 time=1.98 ms
  64 bytes from 10.0.0.2: icmp_seq=4 ttl=255 time=1.98 ms

  --- 10.0.0.2 ping statistics ---
  4 packets transmitted, 4 received, 0% packet loss, time 3008ms
  rtt min/avg/max/mdev = 1.055/1.729/1.989/0.395 ms

.. _`other proposals`: https://www.isc.org/othersoftware/
.. _`Hurricane Electric`: https://tunnelbroker.net/
