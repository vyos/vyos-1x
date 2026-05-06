###########
BGP Example
###########

**Policy definition:**

.. code-block:: none

  # Create policy
  set policy route-map setmet rule 2 action 'permit'
  set policy route-map setmet rule 2 set as-path prepend '2 2 2'

  # Apply policy to BGP
  set protocols bgp system-as 1
  set protocols bgp neighbor 203.0.113.2 address-family ipv4-unicast route-map import 'setmet'
  set protocols bgp neighbor 203.0.113.2 address-family ipv4-unicast soft-reconfiguration 'inbound'

Using 'soft-reconfiguration' we get the policy update without bouncing the
neighbor.

**Routes learned before routing policy applied:**

.. code-block:: none

  vyos@vos1:~$ show ip bgp
  BGP table version is 0, local router ID is 192.168.56.101
  Status codes: s suppressed, d damped, h history, * valid, > best, i - internal,
                r RIB-failure, S Stale, R Removed
  Origin codes: i - IGP, e - EGP, ? - incomplete

     Network          Next Hop            Metric LocPrf Weight Path
  *> 198.51.100.3/32   203.0.113.2           1             0 2 i  < Path

  Total number of prefixes 1

**Routes learned after routing policy applied:**

.. code-block:: none

  vyos@vos1:~$ show ip bgp
  BGP table version is 0, local router ID is 192.168.56.101
  Status codes: s suppressed, d damped, h history, * valid, > best, i - internal,
                r RIB-failure, S Stale, R Removed
  Origin codes: i - IGP, e - EGP, ? - incomplete

     Network          Next Hop            Metric LocPrf Weight Path
  *> 198.51.100.3/32   203.0.113.2           1             0 2 2 2 2 i

  Total number of prefixes 1
  vyos@vos1:~$

You now see the longer AS path.

#################
Transparent Proxy
#################

The following example will show how VyOS can be used to redirect web
traffic to an external transparent proxy:

.. code-block:: none

  set policy route FILTER-WEB rule 1000 destination port 80
  set policy route FILTER-WEB rule 1000 protocol tcp
  set policy route FILTER-WEB rule 1000 set table 100

This creates a route policy called FILTER-WEB with one rule to set the
routing table for matching traffic (TCP port 80) to table ID 100
instead of the default routing table.

To create routing table 100 and add a new default gateway to be used by
traffic matching our route policy:

.. code-block:: none

  set protocols static table 100 route 0.0.0.0/0 next-hop 10.255.0.2

This can be confirmed using the ``show ip route table 100`` operational
command.

Finally, to apply the policy route to ingress traffic on our LAN
interface, we use:

.. code-block:: none

  set policy route FILTER-WEB interface eth1

################
Multiple Uplinks
################

VyOS Policy-Based Routing (PBR) works by matching source IP address
ranges and forwarding the traffic using different routing tables.

Routing tables that will be used in this example are:

* ``table 10`` Routing table used for VLAN 10 (192.168.188.0/24)
* ``table 11`` Routing table used for VLAN 11 (192.168.189.0/24)
* ``main`` Routing table used by VyOS and other interfaces not
  participating in PBR

.. figure:: /_static/images/pbr_example_1.*
   :scale: 80 %
   :alt: PBR multiple uplinks

   Policy-Based Routing with multiple ISP uplinks
   (source ./draw.io/pbr_example_1.drawio)

Add default routes for routing ``table 10`` and ``table 11``

.. code-block:: none

  set protocols static table 10 route 0.0.0.0/0 next-hop 192.0.1.1
  set protocols static table 11 route 0.0.0.0/0 next-hop 192.0.2.2

Add policy route matching VLAN source addresses

.. code-block:: none

  set policy route PBR rule 20 set table '10'
  set policy route PBR rule 20 description 'Route VLAN10 traffic to table 10'
  set policy route PBR rule 20 source address '192.168.188.0/24'

  set policy route PBR rule 30 set table '11'
  set policy route PBR rule 30 description 'Route VLAN11 traffic to table 11'
  set policy route PBR rule 30 source address '192.168.189.0/24'

Apply routing policy to **inbound** direction of out VLAN interfaces

.. code-block:: none

  set policy route 'PBR' interface eth0.10
  set policy route 'PBR' interface eth0.11


**OPTIONAL:** Exclude Inter-VLAN traffic (between VLAN10 and VLAN11)
from PBR

.. code-block:: none

  set firewall group network-group VLANS-GR description 'VLANs networks'
  set firewall group network-group VLANS-GR network '192.168.188.0/24'
  set firewall group network-group VLANS-GR network '192.168.189.0/24'

  set policy route PBR rule 10 description 'VLAN10 <-> VLAN11 shortcut'
  set policy route PBR rule 10 destination group network-group 'VLANS-GR'
  set policy route PBR rule 10 set table 'main'

These commands allow the VLAN10 and VLAN11 hosts to communicate with
each other using the main routing table.

Local route
===========

The following example allows VyOS to use :abbr:`PBR (Policy-Based Routing)`
for traffic, which originated from the router itself. That solution for multiple
ISP's and VyOS router will respond from the same interface that the packet was
received. Also, it used, if we want that one VPN tunnel to be through one
provider, and the second through another.

* ``203.0.113.254`` IP addreess on VyOS eth1 from ISP1
* ``192.168.2.254`` IP addreess on VyOS eth2 from ISP2
* ``table 10`` Routing table used for ISP1
* ``table 11`` Routing table used for ISP2


.. code-block:: none

  set policy local-route rule 101 set table '10'
  set policy local-route rule 101 source address '203.0.113.254'
  set policy local-route rule 102 set table '11'
  set policy local-route rule 102 source address '192.0.2.254'
  set protocols static table 10 route 0.0.0.0/0 next-hop '203.0.113.1'
  set protocols static table 11 route 0.0.0.0/0 next-hop '192.0.2.2'

Add multiple source IP in one rule with same priority

.. code-block:: none

  set policy local-route rule 101 set table '10'
  set policy local-route rule 101 source address '203.0.113.254'
  set policy local-route rule 101 source address '203.0.113.253'
  set policy local-route rule 101 source address '198.51.100.0/24'

###########################
Clamp MSS for a specific IP
###########################

This example shows how to target an MSS clamp (in our example to 1360 bytes) 
to a specific destination IP.

.. code-block:: none

  set policy route IP-MSS-CLAMP rule 10 description 'Clamp TCP session MSS to 1360 for 198.51.100.30'
  set policy route IP-MSS-CLAMP rule 10 destination address '198.51.100.30/32'
  set policy route IP-MSS-CLAMP rule 10 protocol 'tcp'
  set policy route IP-MSS-CLAMP rule 10 set tcp-mss '1360'
  set policy route IP-MSS-CLAMP rule 10 tcp flags 'SYN'

To apply this policy to the correct interface, configure it on the 
interface the inbound local host will send through to reach our 
destined target host (in our example eth1).

.. code-block:: none

  set policy route IP-MSS-CLAMP interface eth1

You can view that the policy is being correctly (or incorrectly) utilised
with the following command:

.. code-block:: none

  show policy route statistics
