:lastproofread: 2025-06-26

.. _examples-ipsec-cisco-route-based:

#########################################################
Route-based Site-to-Site VPN IPsec between VyOS and Cisco
#########################################################

This document is to describe a basic setup using route-based
site-to-site VPN IPsec. In this example we use VyOS 1.5 and
Cisco IOS. Cisco initiates IPsec connection only if interesting
traffic present. For stable work we recommend configuring an
initiator role on VyOS side. OSPF is selected as routing protocol
inside the tunnel.

Network Topology
================

.. image:: /_static/images/cisco-vpn-ipsec.*
   :align: center
   :alt: Network Topology Diagram

Prerequirements
===============

**VyOS:**

+---------+----------------+
| WAN IP  |  10.0.1.2/30   |
+---------+----------------+
| LAN1 IP | 192.168.0.1/24 |
+---------+----------------+
| LAN2 IP | 192.168.1.1/24 |
+---------+----------------+

**Cisco:**

+---------+-----------------+
| WAN IP  | 10.0.2.2/30     |
+---------+-----------------+
| LAN1 IP | 192.168.10.1/24 |
+---------+-----------------+
| LAN2 IP | 192.168.11.1/24 |
+---------+-----------------+

**IKE parameters:**

+-------------------+---------+
| Encryption        | AES-128 |
+-------------------+---------+
| HASH              | SHA-1   |
+-------------------+---------+
| Diff-Helman Group | 14      |
+-------------------+---------+
| Life-Time         | 28800   |
+-------------------+---------+
| IKE Version       | 1       |
+-------------------+---------+

**IPsec parameters:**

+------------+---------+
| Encryption | AES-256 |
+------------+---------+
| HASH       | SHA-256 |
+------------+---------+
| Life-Time  | 3600    |
+------------+---------+
| PFS        | disable |
+------------+---------+

**Hosts configuration**

+--------+--------------+
| PC1 IP | 192.168.0.2  |
+--------+--------------+
| PC2 IP | 192.168.1.2  |
+--------+--------------+
| PC3 IP | 192.168.10.2 |
+--------+--------------+
| PC4 IP | 192.168.11.2 |
+--------+--------------+

Configuration
=============

.. note:: Pfs is disabled in Cisco by default.

VyOS
----

.. stop_vyoslinter

.. code-block:: none

 set interfaces ethernet eth0 address '10.0.1.2/30'
 set interfaces ethernet eth1 address '192.168.0.1/24'
 set interfaces ethernet eth2 address '192.168.1.1/24'
 set interfaces vti vti1 address '10.100.100.1/30'
 set interfaces vti vti1 mtu '1438'
 set protocols ospf area 0 network '10.100.100.0/30'
 set protocols ospf area 0 network '192.168.0.0/24'
 set protocols ospf area 0 network '192.168.1.0/24'
 set protocols ospf interface eth1 passive
 set protocols ospf interface eth2 passive
 set protocols ospf interface vti1 network 'point-to-point'
 set protocols ospf parameters router-id '2.2.2.2'
 set protocols static route 0.0.0.0/0 next-hop 10.0.1.1
 set vpn ipsec authentication psk AUTH-PSK id '10.0.1.2'
 set vpn ipsec authentication psk AUTH-PSK id '10.0.2.2'
 set vpn ipsec authentication psk AUTH-PSK secret 'dGVzdA=='
 set vpn ipsec authentication psk AUTH-PSK secret-type 'base64'
 set vpn ipsec esp-group ESP-GROUP lifetime '3600'
 set vpn ipsec esp-group ESP-GROUP pfs 'disable'
 set vpn ipsec esp-group ESP-GROUP proposal 10 encryption 'aes256'
 set vpn ipsec esp-group ESP-GROUP proposal 10 hash 'sha256'
 set vpn ipsec ike-group IKE-GROUP close-action 'start'
 set vpn ipsec ike-group IKE-GROUP dead-peer-detection action 'restart'
 set vpn ipsec ike-group IKE-GROUP dead-peer-detection interval '10'
 set vpn ipsec ike-group IKE-GROUP dead-peer-detection timeout '30'
 set vpn ipsec ike-group IKE-GROUP key-exchange 'ikev1'
 set vpn ipsec ike-group IKE-GROUP lifetime '28800'
 set vpn ipsec ike-group IKE-GROUP proposal 10 dh-group '14'
 set vpn ipsec ike-group IKE-GROUP proposal 10 encryption 'aes128'
 set vpn ipsec ike-group IKE-GROUP proposal 10 hash 'sha1'
 set vpn ipsec options disable-route-autoinstall
 set vpn ipsec site-to-site peer CISCO authentication local-id '10.0.1.2'
 set vpn ipsec site-to-site peer CISCO authentication mode 'pre-shared-secret'
 set vpn ipsec site-to-site peer CISCO authentication remote-id '10.0.2.2'
 set vpn ipsec site-to-site peer CISCO connection-type 'initiate'
 set vpn ipsec site-to-site peer CISCO default-esp-group 'ESP-GROUP'
 set vpn ipsec site-to-site peer CISCO ike-group 'IKE-GROUP'
 set vpn ipsec site-to-site peer CISCO local-address '10.0.1.2'
 set vpn ipsec site-to-site peer CISCO remote-address '10.0.2.2'
 set vpn ipsec site-to-site peer CISCO vti bind 'vti1'

.. start_vyoslinter

Cisco
-----

.. stop_vyoslinter

.. code-block:: none

 crypto isakmp policy 10
  encr aes
  authentication pre-share
  group 14
  lifetime 28800
 crypto isakmp key test address 10.0.1.2
 !
 !
 crypto ipsec transform-set TS esp-aes 256 esp-sha256-hmac
  mode transport
 !
 crypto ipsec profile IPsec-profile
  set transform-set TS
 !
 !
 !
 !
 !
 !
 !
 interface Loopback0
  ip address 1.1.1.1 255.255.255.255
 !
 interface Tunnel10
  ip address 10.100.100.2 255.255.255.252
  ip ospf network point-to-point
  tunnel source GigabitEthernet0/0
  tunnel mode ipsec ipv4
  tunnel destination 10.0.1.2
  tunnel protection ipsec profile IPsec-profile
 !
 interface GigabitEthernet0/0
  ip address 10.0.2.2 255.255.255.252
  duplex auto
  speed auto
  media-type rj45
 !
 interface GigabitEthernet0/1
  ip address 192.168.10.1 255.255.255.0
  duplex auto
  speed auto
  media-type rj45
 !
 interface GigabitEthernet0/2
  ip address 192.168.11.1 255.255.255.0
  duplex auto
  speed auto
  media-type rj45
 !
 router ospf 1
  router-id 1.1.1.1
  passive-interface GigabitEthernet0/1
  passive-interface GigabitEthernet0/2
  network 10.100.100.0 0.0.0.3 area 0
  network 192.168.10.0 0.0.0.255 area 0
  network 192.168.11.0 0.0.0.255 area 0
 !
 ip route 0.0.0.0 0.0.0.0 10.0.2.1

.. start_vyoslinter


Monitoring
==========

Monitoring on VyOS side
-----------------------

IKE SAs:

.. code-block:: none

 vyos@vyos:~$ show vpn ike sa
 Peer ID / IP                            Local ID / IP
 ------------                            -------------
 10.0.2.2 10.0.2.2                       10.0.1.2 10.0.1.2

     State  IKEVer  Encrypt      Hash          D-H Group      NAT-T  A-Time  L-Time
     -----  ------  -------      ----          ---------      -----  ------  ------
     up     IKEv1   AES_CBC_128  HMAC_SHA1_96  MODP_2048      no     8175    18439



IPsec SAs:

.. code-block:: none

 vyos@vyos:~$ show vpn ipsec sa
 Connection    State    Uptime    Bytes In/Out    Packets In/Out    Remote address    Remote ID    Proposal
 ------------  -------  --------  --------------  ----------------  ----------------  -----------  -----------------------------
 CISCO-vti     up       34m59s    17K/14K         224/213           10.0.2.2          10.0.2.2     AES_CBC_256/HMAC_SHA2_256_128

OSPF Neighbor Status:

.. stop_vyoslinter

.. code-block:: none

 vyos@vyos:~$ show ip ospf neighbor

 Neighbor ID     Pri State           Up Time         Dead Time Address         Interface                        RXmtL RqstL DBsmL
 1.1.1.1           1 Full/-          1h29m37s          39.317s 10.100.100.2    vti1:10.100.100.1                    0     0     0

.. start_vyoslinter

Routing Table:

.. code-block:: none

 vyos@vyos:~$ show ip route
 Codes: K - kernel route, C - connected, L - local, S - static,
        R - RIP, O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
        T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
        f - OpenFabric, t - Table-Direct,
        > - selected route, * - FIB route, q - queued, r - rejected, b - backup
        t - trapped, o - offload failure


 S>* 0.0.0.0/0 [1/0] via 10.0.1.1, eth0, weight 1, 00:07:54
 C>* 10.0.1.0/30 is directly connected, eth0, weight 1, 00:07:59
 L>* 10.0.1.2/32 is directly connected, eth0, weight 1, 00:07:59
 O   10.100.100.0/30 [110/1] is directly connected, vti1, weight 1, 00:07:50
 C>* 10.100.100.0/30 is directly connected, vti1, weight 1, 00:07:50
 L>* 10.100.100.1/32 is directly connected, vti1, weight 1, 00:07:50
 O   192.168.0.0/24 [110/1] is directly connected, eth1, weight 1, 00:07:54
 C>* 192.168.0.0/24 is directly connected, eth1, weight 1, 00:07:59
 L>* 192.168.0.1/32 is directly connected, eth1, weight 1, 00:07:59
 O   192.168.1.0/24 [110/1] is directly connected, eth2, weight 1, 00:07:54
 C>* 192.168.1.0/24 is directly connected, eth2, weight 1, 00:07:59
 L>* 192.168.1.1/32 is directly connected, eth2, weight 1, 00:07:59
 O>* 192.168.10.0/24 [110/2] via 10.100.100.2, vti1, weight 1, 00:07:34
 O>* 192.168.11.0/24 [110/2] via 10.100.100.2, vti1, weight 1, 00:07:34

Monitoring on Cisco side
------------------------

.. stop_vyoslinter

IKE SAs:

.. code-block:: none

 Cisco#show crypto isakmp sa
 IPv4 Crypto ISAKMP SA
 dst             src             state          conn-id status
 10.0.1.2        10.0.2.2        QM_IDLE           1002 ACTIVE

 IPv6 Crypto ISAKMP SA



IPsec SAs:

.. code-block:: none

 Cisco#show crypto ipsec sa

 interface: Tunnel10
     Crypto map tag: Tunnel10-head-0, local addr 10.0.2.2

    protected vrf: (none)
    local  ident (addr/mask/prot/port): (0.0.0.0/0.0.0.0/0/0)
    remote ident (addr/mask/prot/port): (0.0.0.0/0.0.0.0/0/0)
    current_peer 10.0.1.2 port 500
      PERMIT, flags={origin_is_acl,}
     #pkts encaps: 1295, #pkts encrypt: 1295, #pkts digest: 1295
     #pkts decaps: 1238, #pkts decrypt: 1238, #pkts verify: 1238
     #pkts compressed: 0, #pkts decompressed: 0
     #pkts not compressed: 0, #pkts compr. failed: 0
     #pkts not decompressed: 0, #pkts decompress failed: 0
     #send errors 0, #recv errors 0

      local crypto endpt.: 10.0.2.2, remote crypto endpt.: 10.0.1.2
      plaintext mtu 1438, path mtu 1500, ip mtu 1500, ip mtu idb GigabitEthernet0/0
      current outbound spi: 0xC3E9B307(3286872839)
      PFS (Y/N): N, DH group: none

      inbound esp sas:
       spi: 0x2740C328(658555688)
         transform: esp-256-aes esp-sha256-hmac ,
         in use settings ={Tunnel, }
         conn id: 7, flow_id: SW:7, sibling_flags 80000040, crypto map: Tunnel10-head-0
         sa timing: remaining key lifetime (k/sec): (4173824/1401)
         IV size: 16 bytes
         replay detection support: Y
         Status: ACTIVE(ACTIVE)

      inbound ah sas:

      inbound pcp sas:

      outbound esp sas:
       spi: 0xC3E9B307(3286872839)
         transform: esp-256-aes esp-sha256-hmac ,
         in use settings ={Tunnel, }
         conn id: 8, flow_id: SW:8, sibling_flags 80000040, crypto map: Tunnel10-head-0
         sa timing: remaining key lifetime (k/sec): (4173819/1401)
         IV size: 16 bytes
         replay detection support: Y
         Status: ACTIVE(ACTIVE)

      outbound ah sas:

      outbound pcp sas:

OSPF Neighbor Status:

.. code-block:: none

 Cisco# show ip ospf neighbor

 Neighbor ID     Pri   State           Dead Time   Address         Interface
 2.2.2.2           0   FULL/  -        00:00:35    10.100.100.1    Tunnel10

Routing Table:

.. code-block:: none

 Cisco#show ip route
 Codes: L - local, C - connected, S - static, R - RIP, M - mobile, B - BGP
        D - EIGRP, EX - EIGRP external, O - OSPF, IA - OSPF inter area
        N1 - OSPF NSSA external type 1, N2 - OSPF NSSA external type 2
        E1 - OSPF external type 1, E2 - OSPF external type 2
        i - IS-IS, su - IS-IS summary, L1 - IS-IS level-1, L2 - IS-IS level-2
        ia - IS-IS inter area, * - candidate default, U - per-user static route
        o - ODR, P - periodic downloaded static route, H - NHRP, l - LISP
        a - application route
        + - replicated route, % - next hop override, p - overrides from PfR

 Gateway of last resort is 10.0.2.1 to network 0.0.0.0

 S*    0.0.0.0/0 [1/0] via 10.0.2.1
       1.0.0.0/32 is subnetted, 1 subnets
 C        1.1.1.1 is directly connected, Loopback0
       10.0.0.0/8 is variably subnetted, 4 subnets, 2 masks
 C        10.0.2.0/30 is directly connected, GigabitEthernet0/0
 L        10.0.2.2/32 is directly connected, GigabitEthernet0/0
 C        10.100.100.0/30 is directly connected, Tunnel10
 L        10.100.100.2/32 is directly connected, Tunnel10
 O     192.168.0.0/24 [110/1001] via 10.100.100.1, 00:09:36, Tunnel10
 O     192.168.1.0/24 [110/1001] via 10.100.100.1, 00:09:36, Tunnel10
       192.168.10.0/24 is variably subnetted, 2 subnets, 2 masks
 C        192.168.10.0/24 is directly connected, GigabitEthernet0/1
 L        192.168.10.1/32 is directly connected, GigabitEthernet0/1
       192.168.11.0/24 is variably subnetted, 2 subnets, 2 masks
 C        192.168.11.0/24 is directly connected, GigabitEthernet0/2
 L        192.168.11.1/32 is directly connected, GigabitEthernet0/2

.. start_vyoslinter


Checking Connectivity
---------------------

ICMP packets from PC1 to PC3.

.. code-block:: none

 PC1> ping 192.168.10.2

 84 bytes from 192.168.10.2 icmp_seq=1 ttl=62 time=8.479 ms
 84 bytes from 192.168.10.2 icmp_seq=2 ttl=62 time=3.344 ms
 84 bytes from 192.168.10.2 icmp_seq=3 ttl=62 time=3.139 ms
 84 bytes from 192.168.10.2 icmp_seq=4 ttl=62 time=3.176 ms
 84 bytes from 192.168.10.2 icmp_seq=5 ttl=62 time=3.978 ms

ICMP packets from PC2 to PC4.

.. code-block:: none

 PC2> ping 192.168.11.2

 84 bytes from 192.168.11.2 icmp_seq=1 ttl=62 time=9.687 ms
 84 bytes from 192.168.11.2 icmp_seq=2 ttl=62 time=3.286 ms
 84 bytes from 192.168.11.2 icmp_seq=3 ttl=62 time=2.972 ms
