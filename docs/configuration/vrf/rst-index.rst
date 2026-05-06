:lastproofread: 2021-07-07

.. _vrf:

###
VRF
###

:abbr:`VRF (Virtual Routing and Forwarding)` devices combined with ip rules
provides the ability to create virtual routing and forwarding domains (aka
VRFs, VRF-lite to be specific) in the Linux network stack. One use case is the
multi-tenancy problem where each tenant has their own unique routing tables and
in the very least need different default gateways.

Configuration
=============

A VRF device is created with an associated route table. Network interfaces are
then enslaved to a VRF device.

.. cfgcmd:: set vrf name <name> table <id>

   Create a new VRF instance with `<name>` and `<id>`. The name is
   used when placing individual interfaces into the VRF.

   .. note:: A routing table ID can not be modified once it is assigned. It can
      only be changed by deleting and re-adding the VRF instance.

.. cfgcmd:: set vrf bind-to-all

   By default the scope of the port bindings for unbound sockets is limited to
   the default VRF. That is, it will not be matched by packets arriving on
   interfaces enslaved to a VRF and processes may bind to the same port if
   they bind to a VRF.

   TCP & UDP services running in the default VRF context (ie., not bound to any
   VRF device) can work across all VRF domains by enabling this option.

Zebra/Kernel route filtering
----------------------------

Zebra supports prefix-lists and Route Maps to match routes received from
other FRR components. The permit/deny facilities provided by these commands
can be used to filter which routes zebra will install in the kernel.

.. cfgcmd:: set vrf <name> ip protocol <protocol> route-map <route-map>

   Apply a route-map filter to routes for the specified protocol.

   The following protocols can be used: any, babel, bgp, eigrp,
   isis, ospf, rip, static

   .. note:: If you choose any as the option that will cause all protocols that
      are sending routes to zebra.

.. cfgcmd:: set vrf <name> ipv6 protocol <protocol> route-map <route-map>

   Apply a route-map filter to routes for the specified protocol.

   The following protocols can be used: any, babel, bgp, isis,
   ospfv3, ripng, static

   .. note:: If you choose any as the option that will cause all protocols that
      are sending routes to zebra.

Nexthop Tracking
----------------

Nexthop tracking resolve nexthops via the default route by default.
This is enabled by default for a traditional profile of FRR which we
use. It and can be disabled if you do not want to e.g. allow BGP to
peer across the default route.

.. cfgcmd:: set vrf name <name> ip nht no-resolve-via-default

   Do not allow IPv4 nexthop tracking to resolve via the default route. This
   parameter is configured per-VRF, so the command is also available in the VRF
   subnode.

.. cfgcmd:: set vrf name <name> ipv6 nht no-resolve-via-default

   Do not allow IPv6 nexthop tracking to resolve via the default route. This
   parameter is configured per-VRF, so the command is also available in the VRF
   subnode.

Interfaces
----------

When VRFs are used it is not only mandatory to create a VRF but also the VRF
itself needs to be assigned to an interface.

.. cfgcmd:: set interfaces <dummy | ethernet | bonding | bridge | pppoe>
   <interface> vrf <name>

   Assign interface identified by `<interface>` to VRF named `<name>`.

Routing
-------

.. note:: VyOS 1.4 (sagitta) introduced dynamic routing support for VRFs.

Currently dynamic routing is supported for the following protocols:

- :ref:`routing-bgp`
- :ref:`routing-isis`
- :ref:`routing-ospf`
- :ref:`routing-ospfv3`
- :ref:`routing-static`

The CLI configuration is same as mentioned in above articles. The only
difference is, that each routing protocol used, must be prefixed with the `vrf
name <name>` command.

Example
^^^^^^^

The following commands would be required to set options for a given dynamic
routing protocol inside a given vrf:

- :ref:`routing-bgp`: ``set vrf name <name> protocols bgp ...``
- :ref:`routing-isis`: ``set vrf name <name> protocols isis ...``
- :ref:`routing-ospf`: ``set vrf name <name> protocols ospf ...``
- :ref:`routing-ospfv3`: ``set vrf name <name> protocols ospfv3 ...``
- :ref:`routing-static`: ``set vrf name <name> protocols static ...``

Services
-------

Currently the following services can be created isolated in VRFs

- :ref:`dhcp-server`

The CLI configuration is same as mentioned in above articles. The only
difference is, that each service used, must be prefixed with the `vrf
name <name>` command.

Example
^^^^^^^

The following commands would be required to set options for a given service
inside a given vrf:

- :ref:`dhcp-server`: ``set vrf name <name> service dhcp-server ...``
- :ref:`dhcp-server`: ``set vrf name <name> service dhcpv6-server ...``


Operation
=========

It is not sufficient to only configure a VRF but VRFs must be maintained, too.
For VRF maintenance the following operational commands are in place.

.. opcmd:: show vrf

   Lists VRFs that have been created

   .. code-block:: none

     vyos@vyos:~$ show vrf
     VRF name          state     mac address        flags                     interfaces
     --------          -----     -----------        -----                     ----------
     blue              up        00:53:12:d8:74:24  noarp,master,up,lower_up  dum200,eth0.302
     red               up        00:53:de:02:df:aa  noarp,master,up,lower_up  dum100,eth0.300,bond0.100,peth0

   .. note:: Command should probably be extended to list also the real
      interfaces assigned to this one VRF to get a better overview.

.. opcmd:: show vrf <name>

   .. code-block:: none

     vyos@vyos:~$ show vrf name blue
     VRF name          state     mac address        flags                     interfaces
     --------          -----     -----------        -----                     ----------
     blue              up        00:53:12:d8:74:24  noarp,master,up,lower_up  dum200,eth0.302

.. opcmd:: show ip route vrf <name>

   Display IPv4 routing table for VRF identified by `<name>`.

   .. code-block:: none

     vyos@vyos:~$ show ip route vrf blue
     Codes: K - kernel route, C - connected, S - static, R - RIP,
            O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
            T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
            F - PBR, f - OpenFabric,
            > - selected route, * - FIB route, q - queued route, r - rejected route

     VRF blue:
     K   0.0.0.0/0 [255/8192] unreachable (ICMP unreachable), 00:00:50
     S>* 172.16.0.0/16 [1/0] via 192.0.2.1, dum1, 00:00:02
     C>* 192.0.2.0/24 is directly connected, dum1, 00:00:06


.. opcmd:: show ipv6 route vrf <name>

   Display IPv6 routing table for VRF identified by `<name>`.

   .. code-block:: none

     vyos@vyos:~$ show ipv6 route vrf red
     Codes: K - kernel route, C - connected, S - static, R - RIPng,
            O - OSPFv3, I - IS-IS, B - BGP, N - NHRP, T - Table,
            v - VNC, V - VNC-Direct, A - Babel, D - SHARP, F - PBR,
            f - OpenFabric,
            > - selected route, * - FIB route, q - queued route, r - rejected route

     VRF red:
     K   ::/0 [255/8192] unreachable (ICMP unreachable), 00:43:20
     C>* 2001:db8::/64 is directly connected, dum1, 00:02:19
     C>* fe80::/64 is directly connected, dum1, 00:43:19
     K>* ff00::/8 [0/256] is directly connected, dum1, 00:43:19


.. opcmd:: ping <host> vrf <name>

   The ping command is used to test whether a network host is reachable or not.

   Ping uses ICMP protocol's mandatory ECHO_REQUEST datagram to elicit an
   ICMP ECHO_RESPONSE from a host or gateway. ECHO_REQUEST datagrams (pings)
   will have an IP and ICMP header, followed by "struct timeval" and an
   arbitrary number of pad bytes used to fill out the packet.

   When doing fault isolation with ping, you should first run it on the local
   host, to verify that the local network interface is up and running. Then,
   continue with hosts and gateways further down the road towards your
   destination. Round-trip time and packet loss statistics are computed.

   Duplicate packets are not included in the packet loss calculation, although
   the round-trip time of these packets is used in calculating the minimum/
   average/maximum round-trip time numbers.

   .. note:: Ping command can be interrupted at any given time using
     ``<Ctrl>+c``. A brief statistic is shown afterwards.

   .. code-block:: none

     vyos@vyos:~$ ping 192.0.2.1 vrf red
     PING 192.0.2.1 (192.0.2.1) 56(84) bytes of data.
     64 bytes from 192.0.2.1: icmp_seq=1 ttl=64 time=0.070 ms
     64 bytes from 192.0.2.1: icmp_seq=2 ttl=64 time=0.078 ms
     ^C
     --- 192.0.2.1 ping statistics ---
     2 packets transmitted, 2 received, 0% packet loss, time 4ms
     rtt min/avg/max/mdev = 0.070/0.074/0.078/0.004 ms

.. opcmd:: traceroute vrf <name> [ipv4 | ipv6] <host>

   Displays the route packets taken to a network host utilizing VRF instance
   identified by `<name>`. When using the IPv4 or IPv6 option, displays the
   route packets taken to the given hosts IP address family. This option is
   useful when the host is specified as a hostname rather than an IP address.

.. opcmd:: force vrf <name>

   Join a given VRF. This will open a new subshell within the specified VRF.

   The prompt is adjusted to reflect this change in both config and op-mode.

   .. code-block:: none

     vyos@vyos:~$ force vrf blue
     vyos@vyos(vrf:blue):~$

.. _vrf example:

Example
=======

VRF route leaking
-----------------

The following example topology was built using EVE-NG.

.. figure:: /_static/images/vrf-example-topology-01.*
   :alt: VRF topology example

   VRF route leaking

* PC1 is in the ``default`` VRF and acting as e.g. a "fileserver"
* PC2 is in VRF ``blue`` which is the development department
* PC3 and PC4 are connected to a bridge device on router ``R1`` which is in VRF
  ``red``. Say this is the HR department.
* R1 is managed through an out-of-band network that resides in VRF ``mgmt``

.. _vrf example configuration:

Configuration
^^^^^^^^^^^^^

  .. code-block:: none

    set interfaces bridge br10 address '10.30.0.254/24'
    set interfaces bridge br10 member interface eth3
    set interfaces bridge br10 member interface eth4
    set interfaces bridge br10 vrf 'red'

    set interfaces ethernet eth0 address 'dhcp'
    set interfaces ethernet eth0 vrf 'mgmt'
    set interfaces ethernet eth1 address '10.0.0.254/24'
    set interfaces ethernet eth2 address '10.20.0.254/24'
    set interfaces ethernet eth2 vrf 'blue'

    set protocols static route 10.20.0.0/24 interface eth2 vrf 'blue'
    set protocols static route 10.30.0.0/24 interface br10 vrf 'red'

    set service ssh disable-host-validation
    set service ssh vrf 'mgmt'

    set system name-server 'eth0'

    set vrf name blue protocols static route 10.0.0.0/24 interface eth1 vrf 'default'
    set vrf name blue table '3000'
    set vrf name mgmt table '1000'
    set vrf name red protocols static route 10.0.0.0/24 interface eth1 vrf 'default'
    set vrf name red table '2000'

VRF and NAT
-----------

.. _vrf:nat_configuration:

Configuration
^^^^^^^^^^^^^

  .. code-block:: none

    set interfaces ethernet eth0 address '172.16.50.12/24'
    set interfaces ethernet eth0 vrf 'red'

    set interfaces ethernet eth1 address '192.168.130.100/24'
    set interfaces ethernet eth1 vrf 'blue'

    set nat destination rule 110 description 'NAT ssh- INSIDE'
    set nat destination rule 110 destination port '2022'
    set nat destination rule 110 inbound-interface name 'eth0'
    set nat destination rule 110 protocol 'tcp'
    set nat destination rule 110 translation address '192.168.130.40'

    set nat source rule 100 outbound-interface name 'eth0'
    set nat source rule 100 protocol 'all'
    set nat source rule 100 source address '192.168.130.0/24'
    set nat source rule 100 translation address 'masquerade'

    set service ssh vrf 'red'

    set vrf bind-to-all
    set vrf name blue protocols static route 0.0.0.0/0 next-hop 172.16.50.1 vrf 'red'
    set vrf name blue protocols static route 172.16.50.0/24 interface eth0 vrf 'red'
    set vrf name blue table '1010'

    set vrf name red protocols static route 0.0.0.0/0 next-hop 172.16.50.1
    set vrf name red protocols static route 192.168.130.0/24 interface eth1 vrf 'blue'
    set vrf name red table '2020'

.. _vrf example operation:

Operation
^^^^^^^^^

After committing the configuration we can verify all leaked routes are
installed, and try to ICMP ping PC1 from PC3.

  .. code-block:: none

    PCS> ping 10.0.0.1

    84 bytes from 10.0.0.1 icmp_seq=1 ttl=63 time=1.943 ms
    84 bytes from 10.0.0.1 icmp_seq=2 ttl=63 time=1.618 ms
    84 bytes from 10.0.0.1 icmp_seq=3 ttl=63 time=1.745 ms

  .. code-block:: none

    VPCS> show ip

    NAME        : VPCS[1]
    IP/MASK     : 10.30.0.1/24
    GATEWAY     : 10.30.0.254
    DNS         :
    MAC         : 00:50:79:66:68:0f

VRF default routing table
"""""""""""""""""""""""""

  .. code-block:: none

    vyos@R1:~$ show ip route
    Codes: K - kernel route, C - connected, S - static, R - RIP,
           O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
           T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
           F - PBR, f - OpenFabric,
           > - selected route, * - FIB route, q - queued, r - rejected, b - backup

    C>* 10.0.0.0/24 is directly connected, eth1, 00:07:44
    S>* 10.20.0.0/24 [1/0] is directly connected, eth2 (vrf blue), weight 1, 00:07:38
    S>* 10.30.0.0/24 [1/0] is directly connected, br10 (vrf red), weight 1, 00:07:38

VRF red routing table
"""""""""""""""""""""

  .. code-block:: none

    vyos@R1:~$ show ip route vrf red
    Codes: K - kernel route, C - connected, S - static, R - RIP,
           O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
           T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
           F - PBR, f - OpenFabric,
           > - selected route, * - FIB route, q - queued, r - rejected, b - backup

    VRF red:
    K>* 0.0.0.0/0 [255/8192] unreachable (ICMP unreachable), 00:07:57
    S>* 10.0.0.0/24 [1/0] is directly connected, eth1 (vrf default), weight 1, 00:07:40
    C>* 10.30.0.0/24 is directly connected, br10, 00:07:54

VRF blue routing table
""""""""""""""""""""""

  .. code-block:: none

    vyos@R1:~$ show ip route vrf blue
    Codes: K - kernel route, C - connected, S - static, R - RIP,
           O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
           T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
           F - PBR, f - OpenFabric,
           > - selected route, * - FIB route, q - queued, r - rejected, b - backup

    VRF blue:
    K>* 0.0.0.0/0 [255/8192] unreachable (ICMP unreachable), 00:08:00
    S>* 10.0.0.0/24 [1/0] is directly connected, eth1 (vrf default), weight 1, 00:07:44
    C>* 10.20.0.0/24 is directly connected, eth2, 00:07:53


##########
L3VPN VRFs
##########

:abbr:`L3VPN VRFs ( Layer 3 Virtual Private Networks )` bgpd supports for
IPv4 RFC 4364 and IPv6 RFC 4659. L3VPN routes, and their associated VRF
MPLS labels, can be distributed to VPN SAFI neighbors in the default, i.e.,
non VRF, BGP instance. VRF MPLS labels are reached using core MPLS labels
which are distributed using LDP or BGP labeled unicast.
bgpd also supports inter-VRF route leaking.

.. _l3vpn-vrf-route-leaking:

VRF Route Leaking
=================

BGP routes may be leaked (i.e. copied) between a unicast VRF RIB and the VPN
SAFI RIB of the default VRF for use in MPLS-based L3VPNs. Unicast routes may
also be leaked between any VRFs (including the unicast RIB of the default BGP
instance). A shortcut syntax is also available for specifying leaking from
one VRF to another VRF using the default instance’s VPN RIB as the intemediary
. A common application of the VRF-VRF feature is to connect a customer’s
private routing domain to a provider’s VPN service. Leaking is configured from
the point of view of an individual VRF: import refers to routes leaked from VPN
to a unicast VRF, whereas export refers to routes leaked from a unicast VRF to
VPN.


.. note:: Routes exported from a unicast VRF to the VPN RIB must be augmented
          by two parameters:

             an RD / RTLIST

          Configuration for these exported routes must, at a minimum, specify
          these two parameters.

.. _l3vpn-vrf example configuration:

Configuration
=============

Configuration of route leaking between a unicast VRF RIB and the VPN SAFI RIB
of the default VRF is accomplished via commands in the context of a VRF
address-family.

.. cfgcmd:: set vrf name <name> protocols bgp address-family
            <ipv4-unicast|ipv6-unicast> rd vpn export <asn:nn|address:nn>

   Specifies the route distinguisher to be added to a route exported from the
   current unicast VRF to VPN.

.. cfgcmd:: set vrf name <name> protocols bgp address-family
            <ipv4-unicast|ipv6-unicast> route-target vpn <import|export|both>
            [RTLIST]

   Specifies the route-target list to be attached to a route (export) or the
   route-target list to match against (import) when exporting/importing
   between the current unicast VRF and VPN.The RTLIST is a space-separated
   list of route-targets, which are BGP extended community values as
   described in Extended Communities Attribute.

.. cfgcmd:: set vrf name <name> protocols bgp address-family
            <ipv4-unicast|ipv6-unicast> label vpn export <0-1048575|auto>

   Enables an MPLS label to be attached to a route exported from the current
   unicast VRF to VPN. If the value specified is auto, the label value is
   automatically assigned from a pool maintained.

.. cfgcmd:: set vrf name <name> protocols bgp address-family
            <ipv4-unicast|ipv6-unicast> label vpn allocation-mode per-nexthop

   Select how labels are allocated in the given VRF. By default, the per-vrf
   mode is selected, and one label is used for all prefixes from the VRF. The
   per-nexthop will use a unique label for all prefixes that are reachable via
   the same nexthop.

.. cfgcmd:: set vrf name <name> protocols bgp address-family
            <ipv4-unicast|ipv6-unicast> route-map vpn <import|export>
            [route-map <name>]

   Specifies an optional route-map to be applied to routes imported or
   exported between the current unicast VRF and VPN.

.. cfgcmd:: set vrf name <name> protocols bgp address-family
            <ipv4-unicast|ipv6-unicast> <import|export> vpn

   Enables import or export of routes between the current unicast VRF and VPN.

.. cfgcmd:: set vrf name <name> protocols bgp address-family
            <ipv4-unicast|ipv6-unicast> import vrf <name>

   Shortcut syntax for specifying automatic leaking from vrf VRFNAME to the
   current VRF using the VPN RIB as intermediary. The RD and RT are auto
   derived and should not be specified explicitly for either the source or
   destination VRF’s.

.. cfgcmd:: set vrf name <name> protocols bgp address-family
            <ipv4-unicast|ipv6-unicast> route-map vrf import
            [route-map <name>]

   Specifies an optional route-map to be applied to routes imported from VRFs.

.. cfgcmd:: set vrf name <name> protocols bgp interface <interface> mpls
            forwarding

   It is possible to permit BGP install VPN prefixes without transport
   labels. This configuration will install VPN prefixes originated
   from an e-bgp session, and with the next-hop directly connected.

.. _l3vpn-vrf example operation:

Operation
=========

It is not sufficient to only configure a L3VPN VRFs but L3VPN VRFs must be
maintained, too.For L3VPN VRF maintenance the following operational commands
are in place.

.. opcmd:: show bgp <ipv4|ipv6> vpn

   Print active IPV4 or IPV6 routes advertised via the VPN SAFI.

  .. code-block:: none

    BGP table version is 2, local router ID is 10.0.1.1, vrf id 0
    Default local pref 100, local AS 65001
    Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
                   i internal, r RIB-failure, S Stale, R Removed
    Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
    Origin codes:  i - IGP, e - EGP, ? - incomplete

       Network          Next Hop            Metric LocPrf Weight Path
    Route Distinguisher: 10.50.50.1:1011
    *>i10.50.50.0/24    10.0.0.7                  0    100      0 i
        UN=10.0.0.7 EC{65035:1011} label=80 type=bgp, subtype=0
    Route Distinguisher: 10.60.60.1:1011
    *>i10.60.60.0/24    10.0.0.10              0    100      0 i
        UN=10.0.0.10  EC{65035:1011} label=80 type=bgp, subtype=0

.. opcmd:: show bgp <ipv4|ipv6> vpn summary

        Print a summary of neighbor connections for the specified AFI/SAFI
        combination.

  .. code-block:: none

    BGP router identifier 10.0.1.1, local AS number 65001 vrf-id 0
    BGP table version 0
    RIB entries 9, using 1728 bytes of memory
    Peers 4, using 85 KiB of memory
    Peer groups 1, using 64 bytes of memory

    Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt
    10.0.0.7        4      65001      2860      2870        0    0    0 1d23h34m            2       10


.. include:: /_include/common-references.txt
