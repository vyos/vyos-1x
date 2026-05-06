:lastproofread: 2023-04-10

.. _examples-segment-routing-isis:

#############################
Segment-routing IS-IS example
#############################

When utilizing VyOS in an environment with Cisco IOS-XR gear you can use this 
blue print as an initial setup to get MPLS ISIS-SR working between those two 
devices.The lab was build using :abbr:`EVE-NG (Emulated Virtual
Environment NG)`.

.. figure:: /_static/images/vyos-sr-isis.*
   :alt: ISIS-SR network

   ISIS-SR example network

The below configuration is used as example where we keep focus on 
VyOS-P1/VyOS-P2/XRv-P3 which we share the settings.


Configuration
=============

- VyOS-P1:

.. code-block:: none

  set interfaces dummy dum0 address '192.0.2.1/32'
  set interfaces ethernet eth1 address '192.0.2.5/30'
  set interfaces ethernet eth1 mtu '8000'
  set interfaces ethernet eth3 address '192.0.2.21/30'
  set interfaces ethernet eth3 mtu '8000'
  set protocols isis interface dum0 passive
  set protocols isis interface eth1 network point-to-point
  set protocols isis interface eth3 network point-to-point
  set protocols isis level 'level-2'
  set protocols isis log-adjacency-changes
  set protocols isis metric-style 'wide'
  set protocols isis net '49.0000.0000.0000.0001.00'
  set protocols isis segment-routing maximum-label-depth '8'
  set protocols isis segment-routing prefix 192.0.2.1/32 index value '1'
  set protocols mpls interface 'eth1'
  set protocols mpls interface 'eth3'
  set system host-name 'P1-VyOS'

- XRv-P3:

.. code-block:: none

  hostname P3-VyOS
  interface Loopback0
   ipv4 address 192.0.2.3 255.255.255.255
  !
  interface GigabitEthernet0/0/0/1
   mtu 8014
   ipv4 address 192.0.2.6 255.255.255.252
  !
  interface GigabitEthernet0/0/0/2
   mtu 8014
   ipv4 address 192.0.2.18 255.255.255.252
  !
  router isis VyOS
   is-type level-2-only
   net 49.0000.0000.0000.0003.00
   log adjacency changes
   address-family ipv4 unicast
    metric-style wide
    segment-routing mpls
   !
   interface Loopback0
    passive
    address-family ipv4 unicast
     prefix-sid index 3
    !
   !
   interface GigabitEthernet0/0/0/1
    point-to-point
    address-family ipv4 unicast
    !
   !
   interface GigabitEthernet0/0/0/2
    point-to-point
    address-family ipv4 unicast
    !
   !
  !

- VyOS-P2:

.. code-block:: none
  
  set interfaces dummy dum0 address '192.0.2.2/32'
  set interfaces ethernet eth2 address '192.0.2.17/30'
  set interfaces ethernet eth2 mtu '8000'
  set interfaces ethernet eth3 address '192.0.2.26/30'
  set interfaces ethernet eth3 mtu '8000'
  set protocols isis interface dum0 passive
  set protocols isis interface eth2 network point-to-point
  set protocols isis interface eth3 network point-to-point
  set protocols isis level 'level-2'
  set protocols isis log-adjacency-changes
  set protocols isis metric-style 'wide'
  set protocols isis net '49.0000.0000.0000.0002.00'
  set protocols isis segment-routing maximum-label-depth '8'
  set protocols isis segment-routing prefix 192.0.2.2/32 index value '2'
  set protocols mpls interface 'eth2'
  set protocols mpls interface 'eth3'
  set system host-name 'P2-VyOS'

This gives us MPLS segment routing enabled and labels forwarding :

.. code-block:: none
  
   vyos@P1-VyOS:~$ show mpls table
   Inbound Label  Type        Nexthop               Outbound Label
   -----------------------------------------------------------------
   15000          SR (IS-IS)  192.0.2.6             implicit-null
   15001          SR (IS-IS)  192.0.2.22            implicit-null
   15002          SR (IS-IS)  fe80::5200:ff:fe04:3  implicit-null
   16002          SR (IS-IS)  192.0.2.6             16002
   16003          SR (IS-IS)  192.0.2.6             implicit-null
   16011          SR (IS-IS)  192.0.2.22            implicit-null
  
   vyos@P2-VyOS:~$ show mpls table
   Inbound Label  Type        Nexthop     Outbound Label
   -------------------------------------------------------
   15000          SR (IS-IS)  192.0.2.18  implicit-null
   16001          SR (IS-IS)  192.0.2.18  16001
   16003          SR (IS-IS)  192.0.2.18  implicit-null
   16011          SR (IS-IS)  192.0.2.18  16011

   RP/0/0/CPU0:P3-VyOS#show mpls forwarding
   Tue Mar 28 17:47:18.928 UTC
   Local  Outgoing    Prefix             Outgoing     Next Hop        Bytes
   Label  Label       or ID              Interface                    Switched
   ------ ----------- ------------------ ------------ --------------- ------------
   16001  Pop         SR Pfx (idx 1)     Gi0/0/0/1    192.0.2.5       0
   16002  Pop         SR Pfx (idx 2)     Gi0/0/0/2    192.0.2.17      0
   16011  16011       SR Pfx (idx 11)    Gi0/0/0/1    192.0.2.5       0
   24000  Pop         SR Adj (idx 1)     Gi0/0/0/1    192.0.2.5       0
   24001  Pop         SR Adj (idx 3)     Gi0/0/0/1    192.0.2.5       0
   24002  Pop         SR Adj (idx 1)     Gi0/0/0/2    192.0.2.17      0
   24003  Pop         SR Adj (idx 3)     Gi0/0/0/2    192.0.2.17      0


VyOS is able to check MSD per devices: 

.. code-block:: none

   vyos@P1-VyOS:~$ show isis segment-routing node
   Area VyOS:
   IS-IS L1 SR-Nodes:
  
   IS-IS L2 SR-Nodes:
  
   System ID       SRGB           SRLB            Algorithm  MSD
   ---------------------------------------------------------------
   0000.0000.0001  16000 - 23999  15000 - 15999   SPF        8
   0000.0000.0002  16000 - 23999  15000 - 15999   SPF        8
   0000.0000.0003  16000 - 23999  0 - 4294967295  SPF        10
   0000.0000.0011  16000 - 23999  15000 - 15999   SPF        8

   vyos@P2-VyOS:~$ show isis segment-routing node
   Area VyOS:
    IS-IS L1 SR-Nodes:
   
    IS-IS L2 SR-Nodes:
   
    System ID       SRGB           SRLB            Algorithm  MSD
    ---------------------------------------------------------------
    0000.0000.0001  16000 - 23999  15000 - 15999   SPF        8
    0000.0000.0002  16000 - 23999  15000 - 15999   SPF        8
    0000.0000.0003  16000 - 23999  0 - 4294967295  SPF        10
    0000.0000.0011  16000 - 23999  15000 - 15999   SPF        8

Here is the routing tables showing the MPLS segment routing label operations:

.. code-block:: none

   vyos@P1-VyOS:~$ show ip route isis
   Codes: K - kernel route, C - connected, S - static, R - RIP,
          O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
          T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
          f - OpenFabric,
          > - selected route, * - FIB route, q - queued, r - rejected, b - backup
          t - trapped, o - offload failure
   
   I>* 192.0.2.2/32 [115/30] via 192.0.2.6, eth1, label 16002, weight 1, 1d03h18m
   I>* 192.0.2.3/32 [115/10] via 192.0.2.6, eth1, label implicit-null, weight 1, 1d03h18m
   I   192.0.2.4/30 [115/20] via 192.0.2.6, eth1 inactive, weight 1, 1d03h18m
   I>* 192.0.2.11/32 [115/20] via 192.0.2.22, eth3, label implicit-null, weight 1, 1d02h47m
   I>* 192.0.2.16/30 [115/20] via 192.0.2.6, eth1, weight 1, 1d03h18m
   I   192.0.2.20/30 [115/20] via 192.0.2.22, eth3 inactive, weight 1, 1d02h48m
   I>* 192.0.2.24/30 [115/30] via 192.0.2.6, eth1, weight 1, 1d03h18m
   
   
   vyos@P2-VyOS:~$ show ip route isis
   Codes: K - kernel route, C - connected, S - static, R - RIP,
          O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
          T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
          f - OpenFabric,
          > - selected route, * - FIB route, q - queued, r - rejected, b - backup
          t - trapped, o - offload failure
   
   I>* 192.0.2.1/32 [115/30] via 192.0.2.18, eth2, label 16001, weight 1, 1d03h17m
   I>* 192.0.2.3/32 [115/10] via 192.0.2.18, eth2, label implicit-null, weight 1, 1d03h17m
   I>* 192.0.2.4/30 [115/20] via 192.0.2.18, eth2, weight 1, 1d03h17m
   I>* 192.0.2.11/32 [115/40] via 192.0.2.18, eth2, label 16011, weight 1, 1d02h47m
   I   192.0.2.16/30 [115/20] via 192.0.2.18, eth2 inactive, weight 1, 1d03h17m
   I>* 192.0.2.20/30 [115/30] via 192.0.2.18, eth2, weight 1, 1d03h17m
   
   RP/0/0/CPU0:P3-VyOS#show route isis
   Tue Mar 28 18:19:16.417 UTC
   
   i L2 192.0.2.1/32 [115/20] via 192.0.2.5, 1d03h, GigabitEthernet0/0/0/1
   i L2 192.0.2.2/32 [115/20] via 192.0.2.17, 1d03h, GigabitEthernet0/0/0/2
   i L2 192.0.2.11/32 [115/30] via 192.0.2.5, 1d02h, GigabitEthernet0/0/0/1
   i L2 192.0.2.20/30 [115/20] via 192.0.2.5, 1d03h, GigabitEthernet0/0/0/1
   i L2 192.0.2.24/30 [115/20] via 192.0.2.17, 1d03h, GigabitEthernet0/0/0/2

Information about prefix-sid and label-operation from VyOS

.. code-block:: none

   vyos@P1-VyOS:~$ show isis route prefix-sid
   Area VyOS:
   IS-IS L2 IPv4 routing table:
   
    Prefix         Metric  Interface  Nexthop    SID  Label Op.
    ----------------------------------------------------------------------
    192.0.2.1/32   0       -          -          -    -
    192.0.2.2/32   30      eth1       192.0.2.6  2    Swap(16002, 16002)
    192.0.2.3/32   10      eth1       192.0.2.6  3    Pop(16003)
    192.0.2.4/30   20      eth1       192.0.2.6  -    -
    192.0.2.16/30  20      eth1       192.0.2.6  -    -
    192.0.2.20/30  0       -          -          -    -
    192.0.2.24/30  30      eth1       192.0.2.6  -    -

    vyos@P2-VyOS:~$ show isis route prefix-sid
    Area VyOS:
    IS-IS L2 IPv4 routing table:
    
     Prefix         Metric  Interface  Nexthop     SID  Label Op.
     -----------------------------------------------------------------------
     192.0.2.1/32   30      eth2       192.0.2.18  1    Swap(16001, 16001)
     192.0.2.2/32   0       -          -           -    -
     192.0.2.3/32   10      eth2       192.0.2.18  3    Pop(16003)
     192.0.2.4/30   20      eth2       192.0.2.18  -    -
     192.0.2.16/30  20      eth2       192.0.2.18  -    -
     192.0.2.20/30  30      eth2       192.0.2.18  -    -
     192.0.2.24/30  0       -          -           -    -

Ping between VyOS-P1 / VyOS-P2 to confirm reachability:

.. code-block:: none

   vyos@P1-VyOS:~$ ping 192.0.2.2 source-address 192.0.2.1
   PING 192.0.2.2 (192.0.2.2) from 192.0.2.1 : 56(84) bytes of data.
   64 bytes from 192.0.2.2: icmp_seq=1 ttl=63 time=3.47 ms
   64 bytes from 192.0.2.2: icmp_seq=2 ttl=63 time=2.06 ms
   64 bytes from 192.0.2.2: icmp_seq=3 ttl=63 time=3.90 ms
   64 bytes from 192.0.2.2: icmp_seq=4 ttl=63 time=3.87 ms
   ^C
   --- 192.0.2.2 ping statistics ---
   4 packets transmitted, 4 received, 0% packet loss, time 3004ms
   rtt min/avg/max/mdev = 2.064/3.326/3.903/0.748 ms

   vyos@P2-VyOS:~$ ping 192.0.2.1 source-address 192.0.2.2
   PING 192.0.2.1 (192.0.2.1) from 192.0.2.2 : 56(84) bytes of data.
   64 bytes from 192.0.2.1: icmp_seq=1 ttl=63 time=2.91 ms
   64 bytes from 192.0.2.1: icmp_seq=2 ttl=63 time=3.23 ms
   64 bytes from 192.0.2.1: icmp_seq=3 ttl=63 time=2.91 ms
   64 bytes from 192.0.2.1: icmp_seq=4 ttl=63 time=2.85 ms
   ^C
   --- 192.0.2.1 ping statistics ---
   4 packets transmitted, 4 received, 0% packet loss, time 3005ms
   rtt min/avg/max/mdev = 2.846/2.972/3.231/0.151 ms