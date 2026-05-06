.. _examples-site-2-site-cisco:

#############################################
Site-to-Site IPSec VPN to Cisco using FlexVPN
#############################################

This guide shows a sample configuration for FlexVPN site-to-site Internet 
Protocol Security (IPsec)/Generic Routing Encapsulation (GRE) tunnel.

FlexVPN is a newer "solution" for deployment of VPNs and it utilizes IKEv2 as 
the key exchange protocol. The result is a flexible and scalable VPN solution 
that can be easily adapted to fit various network needs. It can also support a 
variety of encryption methods, including AES and 3DES.

The lab was built using EVE-NG.


Configuration
^^^^^^^^^^^^^^

VyOS
=====

- GRE:

.. code-block:: none

  set interfaces tunnel tun1 encapsulation 'gre'
  set interfaces tunnel tun1 ip adjust-mss '1336'
  set interfaces tunnel tun1 mtu '1376'
  set interfaces tunnel tun1 remote '10.1.1.6'
  set interfaces tunnel tun1 source-address '198.51.100.1'


- IPsec:

.. code-block:: none

  set vpn ipsec authentication psk vyos_cisco_l id 'vyos.net’
  set vpn ipsec authentication psk vyos_cisco_l id 'cisco.hub.net'
  set vpn ipsec authentication psk vyos_cisco_l secret 'secret'
  set vpn ipsec esp-group e1 lifetime '3600'
  set vpn ipsec esp-group e1 mode 'tunnel'
  set vpn ipsec esp-group e1 pfs 'disable'
  set vpn ipsec esp-group e1 proposal 1 encryption 'aes128'
  set vpn ipsec esp-group e1 proposal 1 hash 'sha256'
  set vpn ipsec ike-group i1 key-exchange 'ikev2'
  set vpn ipsec ike-group i1 lifetime '28800'
  set vpn ipsec ike-group i1 proposal 1 dh-group '5'
  set vpn ipsec ike-group i1 proposal 1 encryption 'aes256'
  set vpn ipsec ike-group i1 proposal 1 hash 'sha256'
  set vpn ipsec interface 'eth2'
  set vpn ipsec options disable-route-autoinstall
  set vpn ipsec options flexvpn
  set vpn ipsec options interface 'tun1'
  set vpn ipsec options virtual-ip
  set vpn ipsec site-to-site peer cisco_hub authentication local-id 'vyos.net'
  set vpn ipsec site-to-site peer cisco_hub authentication mode 'pre-shared-secret'
  set vpn ipsec site-to-site peer cisco_hub authentication remote-id 'cisco.hub.net'
  set vpn ipsec site-to-site peer cisco_hub connection-type 'initiate'
  set vpn ipsec site-to-site peer cisco_hub default-esp-group 'e1'
  set vpn ipsec site-to-site peer cisco_hub ike-group 'i1'
  set vpn ipsec site-to-site peer cisco_hub local-address '198.51.100.1'
  set vpn ipsec site-to-site peer cisco_hub remote-address '10.1.1.6'
  set vpn ipsec site-to-site peer cisco_hub tunnel 1 local prefix '198.51.100.1/32'
  set vpn ipsec site-to-site peer cisco_hub tunnel 1 protocol 'gre'
  set vpn ipsec site-to-site peer cisco_hub tunnel 1 remote prefix '10.1.1.6/32'
  set vpn ipsec site-to-site peer cisco_hub virtual-address '0.0.0.0'


Cisco
=====
.. code-block:: none

  aaa new-model
  !
  !
  aaa authorization network default local
  !
  crypto ikev2 name-mangler GET_DOMAIN
   fqdn all
   email all
  !
  !
  crypto ikev2 authorization policy vyos
   pool mypool
   aaa attribute list mylist
   route set interface
   route accept any tag 100 distance 5
  !
  crypto ikev2 keyring mykeys
   peer peer1
    identity fqdn vyos.net
    pre-shared-key local secret
    pre-shared-key remote secret
  crypto ikev2 profile my_profile
   match identity remote fqdn vyos.net
   identity local fqdn cisco.hub.net
   authentication remote pre-share
   authentication local pre-share
   keyring local mykeys
   dpd 10 3 periodic
   aaa authorization group psk list local name-mangler GET_DOMAIN
   aaa authorization user psk cached
   virtual-template 1
  !
  !
  !
  crypto ipsec transform-set TSET esp-aes esp-sha256-hmac
   mode tunnel
  !
  !
  crypto ipsec profile my-ipsec-profile
   set transform-set TSET
   set ikev2-profile my_profile
  !
  interface Virtual-Template1 type tunnel
   no ip address
   ip mtu 1376
   ip nhrp network-id 1
   ip nhrp shortcut virtual-template 1
   ip tcp adjust-mss 1336
   tunnel path-mtu-discovery
   tunnel protection ipsec profile my-ipsec-profile
   !
   ip local pool my_pool 172.16.122.1 172.16.122.254


Since the tunnel is a point-to-point GRE tunnel, it behaves like any other 
point-to-point interface (for example: serial, dialer), and it is possible to 
run any Interior Gateway Protocol (IGP)/Exterior Gateway Protocol (EGP) over 
the link in order to exchange routing information

Verification
^^^^^^^^^^^^

.. code-block:: none

  vyos@vyos$ show interfaces
  Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down
  Interface        IP Address                        S/L  Description
  ---------        ----------                        ---  -----------
  eth0             -                                 u/u
  eth1             -                                 u/u
  eth2             198.51.100.1/24                       u/u
  eth3             172.16.1.2/24                     u/u
  lo               127.0.0.1/8                       u/u
                   ::1/128
  tun1             172.16.122.2/32                   u/u

  vyos@vyos:~$ show vpn ipsec sa
  Connection          State    Uptime    Bytes In/Out    Packets In/Out    Remote address    Remote ID              Proposal
  ------------------  -------  --------  --------------  ----------------  ----------------  ---------------------  -----------------------------
  cisco_hub-tunnel-1  up       44m17s    35K/31K         382/367           10.1.1.6          cisco.hub.net  AES_CBC_128/HMAC_SHA2_256_128


  Hub#sh crypto ikev2 sa detailed
   IPv4 Crypto IKEv2  SA

  Tunnel-id Local                 Remote                fvrf/ivrf            Status
  5         10.1.1.6/4500         198.51.100.1/4500         none/none               READY
        Encr: AES-CBC, keysize: 256, PRF: SHA256, Hash: SHA256, DH Grp:5, Auth sign: PSK, Auth verify: PSK
        Life/Active Time: 86400/2694 sec
        CE id: 0, Session-id: 2
        Status Description: Negotiation done
        Local spi: C94EE2DC92A60C47       Remote spi: 9AF0EF151BECF14C
        Local id: cisco.hub.net
        Remote id: vyos.net
        Local req msg id:  269            Remote req msg id:  0
        Local next msg id: 269            Remote next msg id: 0
        Local req queued:  269            Remote req queued:  0
        Local window:      5              Remote window:      1
        DPD configured for 10 seconds, retry 3
        Fragmentation not configured.
        Extended Authentication not configured.
        NAT-T is not detected
        Cisco Trust Security SGT is disabled
        Assigned host addr: 172.16.122.2
