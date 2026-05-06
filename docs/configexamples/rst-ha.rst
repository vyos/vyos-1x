:lastproofread: 2021-06-28

.. _example-high-availability:

#############################
High Availability Walkthrough
#############################

This document walks you through a complete HA setup of two VyOS machines. This
design is based on a VM as the primary router and a physical machine as a
backup, using VRRP, BGP, OSPF, and conntrack sharing.

This document aims to walk you through setting everything up, so
at a point where you can reboot any machine and not lose more than a few
seconds worth of connectivity.

Design
======

This is based on a real-life production design. One of the complex issues
is ensuring you have redundant data INTO your network. We do this with a pair
of Cisco Nexus switches and using Virtual PortChannels that are spanned across
them. As a bonus, this also allows for complete switch failure without
an outage. How you achieve this yourself is left as an exercise to the reader.
But our setup is documented here.

Walkthrough suggestion
----------------------

The ``commit`` command is implied after every section. If you make an error,
``commit`` will warn you and you can fix it before getting too far into things.
Please ensure you commit early and commit often.

If you are following through this document, it is strongly suggested you
complete the entire document, ONLY doing the virtual router1 steps, and then
come back and walk through it AGAIN on the backup hardware router.

This ensures you don't go too fast or miss a step. However, it will make your
life easier to configure the fixed IP address and default route now on the
hardware router.

Example Network
---------------

In this document, we have been allocated 203.0.113.0/24 by our upstream
provider, which we are publishing on VLAN100.

They want us to establish a BGP session to their routers on 192.0.2.11 and
192.0.2.12 from our routers 192.0.2.21 and 192.0.2.22. They are AS 65550 and
we are AS 65551.

Our routers are going to have a floating IP address of 203.0.113.1, and use
.2 and .3 as their fixed IPs.

We are going to use 10.200.201.0/24 for an 'internal' network on VLAN201.

When traffic is originated from the 10.200.201.0/24 network, it will be
masqueraded to 203.0.113.1

For connection between sites, we are running a WireGuard link to two REMOTE
routers and using OSPF over those links to distribute routes. That remote
site is expected to send traffic from anything in 10.201.0.0/16

VLANs
-----

These are the vlans we will be using:

* 50: Upstream, using the 192.0.2.0/24 network allocated by them.
* 100: 'Public' network, using our 203.0.113.0/24 network.
* 201: 'Internal' network, using 10.200.201.0/24

Hardware
--------

* switch1 (Nexus 10gb Switch)
* switch2 (Nexus 10gb Switch)
* compute1 (VMware ESXi 6.5)
* compute2 (VMware ESXi 6.5)
* compute3 (VMware ESXi 6.5)
* router2 (Random 1RU machine with 4 NICs)

Note that router1 is a VM that runs on one of the compute nodes.

Network Cabling
---------------

* From Datacenter - This connects into port 1 on both switches, and is tagged
  as VLAN 50
* Cisco VPC Crossconnect - Ports 39 and 40 bonded between each switch
* Hardware Router - Port 8 of each switch
* compute1 - Port 9 of each switch
* compute2 - Port 10 of each switch
* compute3 - Port 11 of each switch

This is ignoring the extra Out-of-band management networking, which should be
on totally different switches, and a different feed into the rack, and is out
of scope of this.

.. note:: Our implementation uses VMware's Distributed Port Groups, which allows
  VMware to use LACP. This is a part of the ENTERPRISE licence, and is not
  available on a free licence. If you are implementing this and do not have
  access to DPGs, you should not use VMware, and use some other virtualization
  platform instead.


Basic Setup (via console)
=========================

Create your router1 VM. So it can withstand a VM Host failing or a
network link failing. Using VMware, this is achieved by enabling vSphere DRS,
vSphere Availability, and creating a Distributed Port Group that uses LACP.

Many other Hypervisors do this, and I'm hoping that this document will be
expanded to document how to do this for others.

Create an 'All VLANs' network group, that passes all trunked traffic through
to the VM. Attach this network group to router1 as eth0.

.. note:: VMware: You must DISABLE SECURITY on this Port group. Make sure that
   ``Promiscuous Mode``\ , ``MAC address changes`` and ``Forged transmits`` are
   enabled. All of these will be done as part of failover.

Bonding on Hardware Router
--------------------------

Create a LACP bond on the hardware router. We are assuming that eth0 and eth1
are connected to port 8 on both switches, and that those ports are configured
as a Port-Channel.

.. code-block:: none

   set interfaces bonding bond0 description 'Switch Port-Channel'
   set interfaces bonding bond0 hash-policy 'layer2'
   set interfaces bonding bond0 member interface 'eth0'
   set interfaces bonding bond0 member interface 'eth1'
   set interfaces bonding bond0 mode '802.3ad'


Assign external IP addresses
----------------------------

VLAN 100 and 201 will have floating IP addresses, but VLAN50 does not, as this
is talking directly to upstream. Create our IP address on vlan50.

For the hardware router, replace ``eth0`` with ``bond0``. As (almost) every
command is identical, this will not be specified unless different things need
to be performed on different hosts.

.. code-block:: none

   set interfaces ethernet eth0 vif 50 address '192.0.2.21/24'

In this case, the hardware router has a different IP, so it would be

.. code-block:: none

   set interfaces ethernet bond0 vif 50 address '192.0.2.22/24'

Add (temporary) default route
-----------------------------

It is assumed that the routers provided by upstream are capable of acting as a
default router, add that as a static route.

.. code-block:: none

   set protocols static route 0.0.0.0/0 next-hop 192.0.2.11
   commit
   save


Enable SSH
----------

Enable SSH so you can now SSH into the routers, rather than using the console.

.. code-block:: none

   set service ssh
   commit
   save

At this point, you should be able to SSH into both of them, and will no longer
need access to the console (unless you break something!)


VRRP Configuration
==================

We are setting up VRRP so that it does NOT fail back when a machine returns into
service, and it prioritizes router1 over router2.

Internal Network
----------------

This has a floating IP address of 10.200.201.1/24, using virtual router ID 201.
The difference between them is the interface name, hello-source-address, and
peer-address.

**router1**

.. code-block:: none

   set interfaces ethernet eth0 vif 201 address 10.200.201.2/24
   set high-availability vrrp group int hello-source-address '10.200.201.2'
   set high-availability vrrp group int interface 'eth0.201'
   set high-availability vrrp group int peer-address '10.200.201.3'
   set high-availability vrrp group int no-preempt
   set high-availability vrrp group int priority '200'
   set high-availability vrrp group int address '10.200.201.1/24'
   set high-availability vrrp group int vrid '201'


**router2**

.. code-block:: none

   set interfaces ethernet bond0 vif 201 address 10.200.201.3/24
   set high-availability vrrp group int hello-source-address '10.200.201.3'
   set high-availability vrrp group int interface 'bond0.201'
   set high-availability vrrp group int peer-address '10.200.201.2'
   set high-availability vrrp group int no-preempt
   set high-availability vrrp group int priority '100'
   set high-availability vrrp group int address '10.200.201.1/24'
   set high-availability vrrp group int vrid '201'


Public Network
--------------

This has a floating IP address of 203.0.113.1/24, using virtual router ID 113.
The virtual router ID is just a random number between 1 and 254, and can be set
to whatever you want. Best practices suggest you try to keep them unique
enterprise-wide.

**router1**

.. code-block:: none

   set interfaces ethernet eth0 vif 100 address 203.0.113.2/24
   set high-availability vrrp group public hello-source-address '203.0.113.2'
   set high-availability vrrp group public interface 'eth0.100'
   set high-availability vrrp group public peer-address '203.0.113.3'
   set high-availability vrrp group public no-preempt
   set high-availability vrrp group public priority '200'
   set high-availability vrrp group public address '203.0.113.1/24'
   set high-availability vrrp group public vrid '113'

**router2**

.. code-block:: none

   set interfaces ethernet bond0 vif 100 address 203.0.113.3/24
   set high-availability vrrp group public hello-source-address '203.0.113.3'
   set high-availability vrrp group public interface 'bond0.100'
   set high-availability vrrp group public peer-address '203.0.113.2'
   set high-availability vrrp group public no-preempt
   set high-availability vrrp group public priority '100'
   set high-availability vrrp group public address '203.0.113.1/24'
   set high-availability vrrp group public vrid '113'


Create VRRP sync-group
----------------------

The sync group is used to replicate connection tracking. It needs to be assigned
to a random VRRP group, and we are creating a sync group called ``sync`` using
the vrrp group ``int``.

.. code-block:: none

   set high-availability vrrp sync-group sync member 'int'

Testing
-------

At this point, you should be able to see both IP addresses when you run
``show interfaces``\ , and ``show vrrp`` should show both interfaces in MASTER
state (and SLAVE state on router2).

.. code-block:: none

   vyos@router1:~$ show vrrp
   Name      Interface      VRID  State    Last Transition
   --------  -----------  ------  -------  -----------------
   int       eth0.201        201  MASTER   100s
   public    eth0.100        113  MASTER   200s
   vyos@router1:~$


You should be able to ping to and from all the IPs you have allocated.

NAT and conntrack-sync
======================

Masquerade Traffic originating from 10.200.201.0/24 that is heading out the
public interface.

.. note:: We explicitly exclude the primary upstream network so that BGP or
   OSPF traffic doesn't accidentally get NAT'ed.

.. code-block:: none

   set nat source rule 10 destination address '!192.0.2.0/24'
   set nat source rule 10 outbound-interface name 'eth0.50'
   set nat source rule 10 source address '10.200.201.0/24'
   set nat source rule 10 translation address '203.0.113.1'


Configure conntrack-sync and enable helpers
--------------------------------------------

Conntrack helper modules are enabled by default, but they tend to cause more
problems than they're worth in complex networks. You can disable all of them
at one go.

.. code-block:: none

      delete system conntrack modules

Now enable replication between nodes. Replace eth0.201 with bond0.201 on the
hardware router.

.. code-block:: none

   set service conntrack-sync accept-protocol 'tcp,udp,icmp'
   set service conntrack-sync event-listen-queue-size '8'
   set service conntrack-sync failover-mechanism vrrp sync-group 'sync'
   set service conntrack-sync interface eth0.201
   set service conntrack-sync mcast-group '224.0.0.50'
   set service conntrack-sync sync-queue-size '8'

.. _ha:contracktesting:

Testing
-------

The simplest way to test is to look at the connection tracking stats on the
standby hardware router with the command ``show conntrack-sync statistics``.
The numbers should be very close to the numbers on the primary router.

When you have both routers up, you should be able to establish a connection
from a NAT'ed machine out to the internet, reboot the active machine, and that
connection should be preserved, and will not drop out.

OSPF Over WireGuard
===================

Wireguard doesn't have the concept of an up or down link, due to its design.
This complicates AND simplifies using it for network transport, as for reliable
state detection you need to use SOMETHING to detect when the link is down.

If you use a routing protocol itself, you solve two problems at once. This is
only a basic example, and is provided as a starting point.

Configure Wireguard
-------------------

There is plenty of instructions and documentation on setting up Wireguard. The
only important thing you need to remember is to only use one WireGuard
interface per OSPF connection.

We use small /30's from 10.254.60/24 for the point-to-point links.

**router1**

Replace the 203.0.113.3 with whatever the other router's IP address is.

.. code-block:: none

   set interfaces wireguard wg01 address '10.254.60.1/30'
   set interfaces wireguard wg01 description 'router1-to-offsite1'
   set interfaces wireguard wg01 peer OFFSITE1 allowed-ips '0.0.0.0/0'
   set interfaces wireguard wg01 peer OFFSITE1 endpoint '203.0.113.3:50001'
   set interfaces wireguard wg01 peer OFFSITE1 persistent-keepalive '15'
   set interfaces wireguard wg01 peer OFFSITE1 pubkey 'GEFMOWzAyau42/HwdwfXnrfHdIISQF8YHj35rOgSZ0o='
   set interfaces wireguard wg01 port '50001'
   set protocols ospf interface wg01 authentication md5 key-id 1 md5-key 'i360KoCwUGZvPq7e'
   set protocols ospf interface wg01 cost '11'
   set protocols ospf interface wg01 dead-interval '5'
   set protocols ospf interface wg01 hello-interval '1'
   set protocols ospf interface wg01 network 'point-to-point'
   set protocols ospf interface wg01 priority '1'
   set protocols ospf interface wg01 retransmit-interval '5'
   set protocols ospf interface wg01 transmit-delay '1'


**offsite1**

This is connecting back to the STATIC IP of router1, not the floating.

.. code-block:: none

   set interfaces wireguard wg01 address '10.254.60.2/30'
   set interfaces wireguard wg01 description 'offsite1-to-router1'
   set interfaces wireguard wg01 peer ROUTER1 allowed-ips '0.0.0.0/0'
   set interfaces wireguard wg01 peer ROUTER1 endpoint '192.0.2.21:50001'
   set interfaces wireguard wg01 peer ROUTER1 persistent-keepalive '15'
   set interfaces wireguard wg01 peer ROUTER1 pubkey 'CKwMV3ZaLntMule2Kd3G7UyVBR7zE8/qoZgLb82EE2Q='
   set interfaces wireguard wg01 port '50001'
   set protocols ospf interface wg01 authentication md5 key-id 1 md5-key 'i360KoCwUGZvPq7e'
   set protocols ospf interface wg01 cost '11'
   set protocols ospf interface wg01 dead-interval '5'
   set protocols ospf interface wg01 hello-interval '1'
   set protocols ospf interface wg01 network 'point-to-point'
   set protocols ospf interface wg01 priority '1'
   set protocols ospf interface wg01 retransmit-interval '5'
   set protocols ospf interface wg01 transmit-delay '1'

Test WireGuard
--------------

Make sure you can ping 10.254.60.1 and .2 from both routers.

Create Export Filter
--------------------

We only want to export the networks we know. Always do a whitelist on your route
filters, both importing and exporting. A good rule of thumb is
**'If you are not the default router for a network, don't advertise
it'**. This means we explicitly do not want to advertise the 192.0.2.0/24
network (but do want to advertise 10.200.201.0 and 203.0.113.0, which we ARE
the default route for). This filter is applied to ``redistribute connected``.
If we WERE to advertise it, the remote machines would see 192.0.2.21 available
via their default route, establish the connection, and then OSPF would say
'192.0.2.0/24 is available via this tunnel', at which point the tunnel would
break, OSPF would drop the routes, and then 192.0.2.0/24 would be reachable via
default again. This is called 'flapping'.

.. code-block:: none

   set policy access-list 150 description 'Outbound OSPF Redistribution'
   set policy access-list 150 rule 10 action 'permit'
   set policy access-list 150 rule 10 destination any
   set policy access-list 150 rule 10 source inverse-mask '0.0.0.255'
   set policy access-list 150 rule 10 source network '10.200.201.0'
   set policy access-list 150 rule 20 action 'permit'
   set policy access-list 150 rule 20 destination any
   set policy access-list 150 rule 20 source inverse-mask '0.0.0.255'
   set policy access-list 150 rule 20 source network '203.0.113.0'
   set policy access-list 150 rule 100 action 'deny'
   set policy access-list 150 rule 100 destination any
   set policy access-list 150 rule 100 source any


Create Import Filter
--------------------

We only want to import networks we know. Our OSPF peer should only be
advertising networks in the 10.201.0.0/16 range. Note that this is an INVERSE
MATCH. You deny in access-list 100 to accept the route.

.. code-block:: none

   set policy access-list 100 description 'Inbound OSPF Routes from Peers'
   set policy access-list 100 rule 10 action 'deny'
   set policy access-list 100 rule 10 destination any
   set policy access-list 100 rule 10 source inverse-mask '0.0.255.255'
   set policy access-list 100 rule 10 source network '10.201.0.0'
   set policy access-list 100 rule 100 action 'permit'
   set policy access-list 100 rule 100 destination any
   set policy access-list 100 rule 100 source any
   set policy route-map PUBOSPF rule 100 action 'deny'
   set policy route-map PUBOSPF rule 100 match ip address access-list '100'
   set policy route-map PUBOSPF rule 500 action 'permit'


Enable OSPF
-----------

Every router **must** have a unique router-id.
The 'reference-bandwidth' is used because when OSPF was originally designed,
the idea of a link faster than 1gbit was unheard of, and it does not scale
correctly.

.. code-block:: none

   set protocols ospf area 0.0.0.0 authentication 'md5'
   set protocols ospf area 0.0.0.0 network '10.254.60.0/24'
   set protocols ospf auto-cost reference-bandwidth '10000'
   set protocols ospf log-adjacency-changes
   set protocols ospf parameters abr-type 'cisco'
   set protocols ospf parameters router-id '10.254.60.2'
   set system ip protocol ospf route-map PUBOSPF


Test OSPF
---------

When you have enabled OSPF on both routers, you should be able to see each
other with the command ``show ip ospf neighbour``. The state must be 'Full'
or '2-Way'. If it is not, then there is a network connectivity issue between the
hosts. This is often caused by NAT or MTU issues. You should not see any new
routes (unless this is the second pass) in the output of ``show ip route``

Advertise connected routes
==========================

As a reminder, only advertise routes that you are the default router for. This
is why we are NOT announcing the 192.0.2.0/24 network, because if that was
announced into OSPF, the other routers would try to connect to that network
over a tunnel that connects to that network!

.. code-block:: none

   set protocols ospf access-list 150 export 'connected'
   set protocols ospf redistribute connected


You should now be able to see the advertised network on the other host.

Duplicate configuration
-----------------------

At this point, you now need to create the X link between all four routers.
Use amdifferent /30 for each link.

Priorities
----------

Set the cost on the secondary links to be 200. This means that they will not
be used unless the primary links are down.

.. code-block:: none

   set protocols ospf interface wg01 cost '10'
   set protocols ospf interface wg01 cost '200'


This will be visible in 'show ip route'.

BGP
===

BGP is an extremely complex network protocol. An example is provided here.

.. note:: Router id's must be unique.

**router1**


The ``redistribute ospf`` command is there purely as an example of how this can
be expanded. In this walkthrough, it will be filtered by BGPOUT rule 10000, as
it is not 203.0.113.0/24.

.. code-block:: none

   set policy prefix-list BGPOUT description 'BGP Export List'
   set policy prefix-list BGPOUT rule 10 action 'deny'
   set policy prefix-list BGPOUT rule 10 description 'Do not advertise short masks'
   set policy prefix-list BGPOUT rule 10 ge '25'
   set policy prefix-list BGPOUT rule 10 prefix '0.0.0.0/0'
   set policy prefix-list BGPOUT rule 100 action 'permit'
   set policy prefix-list BGPOUT rule 100 description 'Our network'
   set policy prefix-list BGPOUT rule 100 prefix '203.0.113.0/24'
   set policy prefix-list BGPOUT rule 10000 action 'deny'
   set policy prefix-list BGPOUT rule 10000 prefix '0.0.0.0/0'

   set policy route-map BGPOUT description 'BGP Export Filter'
   set policy route-map BGPOUT rule 10 action 'permit'
   set policy route-map BGPOUT rule 10 match ip address prefix-list 'BGPOUT'
   set policy route-map BGPOUT rule 10000 action 'deny'
   set policy route-map BGPPREPENDOUT description 'BGP Export Filter'
   set policy route-map BGPPREPENDOUT rule 10 action 'permit'
   set policy route-map BGPPREPENDOUT rule 10 set as-path prepend '65551 65551 65551'
   set policy route-map BGPPREPENDOUT rule 10 match ip address prefix-list 'BGPOUT'
   set policy route-map BGPPREPENDOUT rule 10000 action 'deny'

   set protocols bgp system-as 65551
   set protocols bgp address-family ipv4-unicast network 192.0.2.0/24
   set protocols bgp address-family ipv4-unicast redistribute connected metric '50'
   set protocols bgp address-family ipv4-unicast redistribute ospf metric '50'
   set protocols bgp neighbor 192.0.2.11 address-family ipv4-unicast route-map export 'BGPOUT'
   set protocols bgp neighbor 192.0.2.11 address-family ipv4-unicast soft-reconfiguration inbound
   set protocols bgp neighbor 192.0.2.11 remote-as '65550'
   set protocols bgp neighbor 192.0.2.11 update-source '192.0.2.21'
   set protocols bgp parameters router-id '192.0.2.21'


**router2**

This is identical, but you use the BGPPREPENDOUT route-map to advertise the
route with a longer path.
