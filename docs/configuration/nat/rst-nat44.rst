.. _nat44:

#####
NAT44
#####

:abbr:`NAT (Network Address Translation)` is a common method of
remapping one IP address space into another by modifying network address
information in the IP header of packets while they are in transit across
a traffic routing device. The technique was originally used as a
shortcut to avoid the need to readdress every host when a network was
moved. It has become a popular and essential tool in conserving global
address space in the face of IPv4 address exhaustion. One
Internet-routable IP address of a NAT gateway can be used for an entire
private network.

IP masquerading is a technique that hides an entire IP address space,
usually consisting of private IP addresses, behind a single IP address
in another, usually public address space. The hidden addresses are
changed into a single (public) IP address as the source address of the
outgoing IP packets so they appear as originating not from the hidden
host but from the routing device itself. Because of the popularity of
this technique to conserve IPv4 address space, the term NAT has become
virtually synonymous with IP masquerading.

As network address translation modifies the IP address information in
packets, NAT implementations may vary in their specific behavior in
various addressing cases and their effect on network traffic. The
specifics of NAT behavior are not commonly documented by vendors of
equipment containing NAT implementations.

The computers on an internal network can use any of the addresses set
aside by the :abbr:`IANA (Internet Assigned Numbers Authority)` for
private addressing (see :rfc:`1918`). These reserved IP addresses are
not in use on the Internet, so an external machine will not directly
route to them. The following addresses are reserved for private use:

* 10.0.0.0 to 10.255.255.255 (CIDR: 10.0.0.0/8)
* 172.16.0.0 to 172.31.255.255 (CIDR: 172.16.0.0/12)
* 192.168.0.0 to 192.168.255.255 (CIDR: 192.168.0.0/16)


If an ISP deploys a :abbr:`CGN (Carrier-grade NAT)`, and uses
:rfc:`1918` address space to number customer gateways, the risk of
address collision, and therefore routing failures, arises when the
customer network already uses an :rfc:`1918` address space.

This prompted some ISPs to develop a policy within the :abbr:`ARIN
(American Registry for Internet Numbers)` to allocate new private
address space for CGNs, but ARIN deferred to the IETF before
implementing the policy indicating that the matter was not a typical
allocation issue but a reservation of addresses for technical purposes
(per :rfc:`2860`).

IETF published :rfc:`6598`, detailing a shared address space for use in
ISP CGN deployments that can handle the same network prefixes occurring
both on inbound and outbound interfaces. ARIN returned address space to
the :abbr:`IANA (Internet Assigned Numbers Authority)` for this
allocation.

The allocated address block is 100.64.0.0/10.

Devices evaluating whether an IPv4 address is public must be updated to
recognize the new address space. Allocating more private IPv4 address
space for NAT devices might prolong the transition to IPv6.

Overview
========

Different NAT Types
-------------------

.. _source-nat:

SNAT
^^^^

:abbr:`SNAT (Source Network Address Translation)` is the most common
form of :abbr:`NAT (Network Address Translation)` and is typically
referred to simply as NAT. To be more correct, what most people refer
to as :abbr:`NAT (Network Address Translation)` is actually the process
of :abbr:`PAT (Port Address Translation)`, or NAT overload. SNAT is
typically used by internal users/private hosts to access the Internet
- the source address is translated and thus kept private.

.. _destination-nat:

DNAT
^^^^

:abbr:`DNAT (Destination Network Address Translation)` changes the
destination address of packets passing through the router, while
:ref:`source-nat` changes the source address of packets. DNAT is
typically used when an external (public) host needs to initiate a
session with an internal (private) host. A customer needs to access a
private service behind the routers public IP. A connection is
established with the routers public IP address on a well known port and
thus all traffic for this port is rewritten to address the internal
(private) host.

.. _bidirectional-nat:

Bidirectional NAT
^^^^^^^^^^^^^^^^^

This is a common scenario where both :ref:`source-nat` and
:ref:`destination-nat` are configured at the same time. It's commonly
used when internal (private) hosts need to establish a connection with
external resources and external systems need to access internal
(private) resources.

NAT, Routing, Firewall Interaction
----------------------------------

There is a very nice picture/explanation in the Vyatta documentation
which should be rewritten here.

NAT Ruleset
-----------

:abbr:`NAT (Network Address Translation)` is configured entirely on a
series of so called `rules`. Rules are numbered and evaluated by the
underlying OS in numerical order! The rule numbers can be changes by
utilizing the :cfgcmd:`rename` and :cfgcmd:`copy` commands.

.. note:: Changes to the NAT system only affect newly established
   connections. Already established connections are not affected.

.. hint:: When designing your NAT ruleset leave some space between
   consecutive rules for later extension. Your ruleset could start with
   numbers 10, 20, 30. You thus can later extend the ruleset and place
   new rules between existing ones.

Rules will be created for both :ref:`source-nat` and
:ref:`destination-nat`.

For :ref:`bidirectional-nat` a rule for both :ref:`source-nat` and
:ref:`destination-nat` needs to be created.

.. _traffic-filters:

Traffic Filters
---------------

Traffic Filters are used to control which packets will have the defined
NAT rules applied. Five different filters can be applied within a NAT
rule.

* **outbound-interface** - applicable only to :ref:`source-nat`. It
  configures the interface which is used for the outside traffic that
  this translation rule applies to. Interface groups, inverted
  selection and wildcard, are also supported.

  Examples:

  .. code-block:: none

    set nat source rule 20 outbound-interface name eth0
    set nat source rule 30 outbound-interface name bond1*
    set nat source rule 20 outbound-interface name !vtun2
    set nat source rule 20 outbound-interface group GROUP1
    set nat source rule 20 outbound-interface group !GROUP2


* **inbound-interface** - applicable only to :ref:`destination-nat`. It
  configures the interface which is used for the inside traffic the
  translation rule applies to. Interface groups, inverted
  selection and wildcard, are also supported.

  Example:

  .. code-block:: none

    set nat destination rule 20 inbound-interface name eth0
    set nat destination rule 30 inbound-interface name bond1*
    set nat destination rule 20 inbound-interface name !vtun2
    set nat destination rule 20 inbound-interface group GROUP1
    set nat destination rule 20 inbound-interface group !GROUP2


* **protocol** - specify which types of protocols this translation rule
  applies to. Only packets matching the specified protocol are NATed.
  By default this applies to `all` protocols.

  Example:

  * Set SNAT rule 20 to only NAT TCP and UDP packets
  * Set DNAT rule 20 to only NAT UDP packets

  .. code-block:: none

    set nat source rule 20 protocol tcp_udp
    set nat destination rule 20 protocol udp

* **source** - specifies which packets the NAT translation rule applies
  to based on the packets source IP address and/or source port. Only
  matching packets are considered for NAT.

  Example:

  * Set SNAT rule 20 to only NAT packets arriving from the 192.0.2.0/24
    network
  * Set SNAT rule 30 to only NAT packets arriving from the 203.0.113.0/24
    network with a source port of 80 and 443

  .. code-block:: none

    set nat source rule 20 source address 192.0.2.0/24
    set nat source rule 30 source address 203.0.113.0/24
    set nat source rule 30 source port 80,443


* **destination** - specify which packets the translation will be
  applied to, only based on the destination address and/or port number
  configured.

  .. note:: If no destination is specified the rule will match on any
     destination address and port.

  Example:

  * Configure SNAT rule (40) to only NAT packets with a destination
    address of 192.0.2.1.

  .. code-block:: none

    set nat source rule 40 destination address 192.0.2.1


Address Conversion
------------------

Every NAT rule has a translation command defined. The address defined
for the translation is the address used when the address information in
a packet is replaced.

Source Address
^^^^^^^^^^^^^^

For :ref:`source-nat` rules the packets source address will be replaced
with the address specified in the translation command. A port
translation can also be specified and is part of the translation
address.

.. note:: The translation address must be set to one of the available
   addresses on the configured `outbound-interface` or it must be set to
   `masquerade` which will use the primary IP address of the
   `outbound-interface` as its translation address.

.. note:: When using NAT for a large number of host systems it
   recommended that a minimum of 1 IP address is used to NAT every 256
   private host systems. This is due to the limit of 65,000 port numbers
   available for unique translations and a reserving an average of
   200-300 sessions per host system.

Example:

* Define a discrete source IP address of 100.64.0.1 for SNAT rule 20
* Use address `masquerade` (the interfaces primary address) on rule 30
* For a large amount of private machines behind the NAT your address
  pool might to be bigger. Use any address in the range 100.64.0.10 -
  100.64.0.20 on SNAT rule 40 when doing the translation


.. code-block:: none

  set nat source rule 20 translation address 100.64.0.1
  set nat source rule 30 translation address 'masquerade'
  set nat source rule 40 translation address 100.64.0.10-100.64.0.20


Destination Address
^^^^^^^^^^^^^^^^^^^

For :ref:`destination-nat` rules the packets destination address will be
replaced by the specified address in the `translation address` command.

Example:

* DNAT rule 10 replaces the destination address of an inbound packet
  with 192.0.2.10

.. code-block:: none

  set nat destination rule 10 translation address 192.0.2.10


Also, in :ref:`destination-nat`, redirection to localhost is supported.
The redirect statement is a special form of dnat which always translates
the destination address to the local host’s one.

Example of redirection:

.. code-block:: none

  set nat destination rule 10 translation redirect port 22

NAT Load Balance
----------------

Advanced configuration can be used in order to apply source or destination NAT,
and within a single rule, be able to define multiple translated addresses,
so NAT balances the translations among them.

NAT Load Balance uses an algorithm that generates a hash and based on it, then
it applies corresponding translation. This hash can be generated randomly, or 
can use data from the ip header: source-address, destination-address,
source-port and/or destination-port. By default, it will generate the hash
randomly.

When defining the translated address, called ``backends``, a ``weight`` must
be configured. This lets the user define load balance distribution according
to their needs. Them sum of all the weights defined for the backends should
be equal to 100. In oder words, the weight defined for the backend is the
percentage of the connections that will receive such backend.

.. cfgcmd:: set nat [source | destination] rule <rule> load-balance hash
   [source-address | destination-address | source-port | destination-port
   | random]
.. cfgcmd:: set nat [source | destination] rule <rule> load-balance backend
  <x.x.x.x> weight <1-100>


Configuration Examples
======================

To setup SNAT, we need to know:

* The internal IP addresses we want to translate
* The outgoing interface to perform the translation on
* The external IP address to translate to

In the example used for the Quick Start configuration above, we
demonstrate the following configuration:

.. code-block:: none

  set nat source rule 100 outbound-interface name 'eth0'
  set nat source rule 100 source address '192.168.0.0/24'
  set nat source rule 100 translation address 'masquerade'

Which generates the following configuration:

.. code-block:: none

  rule 100 {
      outbound-interface {
          name eth0
      }
      source {
          address 192.168.0.0/24
      }
      translation {
          address masquerade
      }
  }

In this example, we use **masquerade** as the translation address
instead of an IP address. The **masquerade** target is effectively an
alias to say "use whatever IP address is on the outgoing interface",
rather than a statically configured IP address. This is useful if you
use DHCP for your outgoing interface and do not know what the external
address will be.

When using NAT for a large number of host systems it recommended that a
minimum of 1 IP address is used to NAT every 256 host systems. This is
due to the limit of 65,000 port numbers available for unique
translations and a reserving an average of 200-300 sessions per host
system.

Example: For an ~8,000 host network a source NAT pool of 32 IP addresses
is recommended.

A pool of addresses can be defined by using a hyphen between two IP
addresses:

.. code-block:: none

  set nat source rule 100 translation address '203.0.113.32-203.0.113.63'

.. _avoidng_leaky_nat:

Avoiding "leaky" NAT
--------------------

Linux netfilter will not NAT traffic marked as INVALID. This often
confuses people into thinking that Linux (or specifically VyOS) has a
broken NAT implementation because non-NATed traffic is seen leaving an
external interface. This is actually working as intended, and a packet
capture of the "leaky" traffic should reveal that the traffic is either
an additional TCP "RST", "FIN,ACK", or "RST,ACK" sent by client systems
after Linux netfilter considers the connection closed. The most common
is the additional TCP RST some host implementations send after
terminating a connection (which is implementation-specific).

In other words, connection tracking has already observed the connection
be closed and has transition the flow to INVALID to prevent attacks from
attempting to reuse the connection.

You can avoid the "leaky" behavior by using a firewall policy that drops
"invalid" state packets.

Having control over the matching of INVALID state traffic, e.g. the
ability to selectively log, is an important troubleshooting tool for
observing broken protocol behavior. For this reason, VyOS does not
globally drop invalid state traffic, instead allowing the operator to
make the determination on how the traffic is handled.

.. _hairpin_nat_reflection:

Hairpin NAT/NAT Reflection
--------------------------

A typical problem with using NAT and hosting public servers is the
ability for internal systems to reach an internal server using it's
external IP address. The solution to this is usually the use of
split-DNS to correctly point host systems to the internal address when
requests are made internally. Because many smaller networks lack DNS
infrastructure, a work-around is commonly deployed to facilitate the
traffic by NATing the request from internal hosts to the source address
of the internal interface on the firewall.

This technique is commonly referred to as NAT Reflection or Hairpin NAT.

Example:

* Redirect Microsoft RDP traffic from the outside (WAN, external) world
  via :ref:`destination-nat` in rule 100 to the internal, private host
  192.0.2.40.

* Redirect Microsoft RDP traffic from the internal (LAN, private)
  network via :ref:`destination-nat` in rule 110 to the internal,
  private host 192.0.2.40. We also need a :ref:`source-nat` rule 110 for
  the reverse path of the traffic. The internal network 192.0.2.0/24 is
  reachable via interface `eth0.10`.

.. code-block:: none

  set nat destination rule 100 description 'Regular destination NAT from external'
  set nat destination rule 100 destination port '3389'
  set nat destination rule 100 inbound-interface name 'pppoe0'
  set nat destination rule 100 protocol 'tcp'
  set nat destination rule 100 translation address '192.0.2.40'

  set nat destination rule 110 description 'NAT Reflection: INSIDE'
  set nat destination rule 110 destination port '3389'
  set nat destination rule 110 inbound-interface name 'eth0.10'
  set nat destination rule 110 protocol 'tcp'
  set nat destination rule 110 translation address '192.0.2.40'

  set nat source rule 110 description 'NAT Reflection: INSIDE'
  set nat source rule 110 destination address '192.0.2.0/24'
  set nat source rule 110 outbound-interface name 'eth0.10'
  set nat source rule 110 protocol 'tcp'
  set nat source rule 110 source address '192.0.2.0/24'
  set nat source rule 110 translation address 'masquerade'

Which results in a configuration of:

.. code-block:: none

  vyos@vyos# show nat
   destination {
       rule 100 {
           description "Regular destination NAT from external"
           destination {
               port 3389
           }
           inbound-interface {
               name pppoe0
           }
           protocol tcp
           translation {
               address 192.0.2.40
           }
       }
       rule 110 {
           description "NAT Reflection: INSIDE"
           destination {
               port 3389
           }
           inbound-interface {
               name eth0.10
           }
           protocol tcp
           translation {
               address 192.0.2.40
           }
       }
   }
   source {
       rule 110 {
           description "NAT Reflection: INSIDE"
           destination {
               address 192.0.2.0/24
           }
           outbound-interface {
               name eth0.10
           }
           protocol tcp
           source {
               address 192.0.2.0/24
           }
           translation {
               address masquerade
           }
       }
   }


Destination NAT
---------------

DNAT is typically referred to as a **Port Forward**. When using VyOS as
a NAT router and firewall, a common configuration task is to redirect
incoming traffic to a system behind the firewall.

In this example, we will be using the example Quick Start configuration
above as a starting point.

To setup a destination NAT rule we need to gather:

* The interface traffic will be coming in on;
* The protocol and port we wish to forward;
* The IP address of the internal system we wish to forward traffic to.

In our example, we will be forwarding web server traffic to an internal
web server on 192.168.0.100. HTTP traffic makes use of the TCP protocol
on port 80. For other common port numbers, see:
https://en.wikipedia.org/wiki/List_of_TCP_and_UDP_port_numbers

Our configuration commands would be:

.. code-block:: none

  set nat destination rule 10 description 'Port Forward: HTTP to 192.168.0.100'
  set nat destination rule 10 destination port '80'
  set nat destination rule 10 inbound-interface name 'eth0'
  set nat destination rule 10 protocol 'tcp'
  set nat destination rule 10 translation address '192.168.0.100'

Which would generate the following NAT destination configuration:

.. code-block:: none

  nat {
      destination {
          rule 10 {
              description "Port Forward: HTTP to 192.168.0.100"
              destination {
                  port 80
              }
              inbound-interface {
                  name eth0
              }
              protocol tcp
              translation {
                  address 192.168.0.100
              }
          }
      }
  }

.. note:: If forwarding traffic to a different port than it is arriving
   on, you may also configure the translation port using
   `set nat destination rule [n] translation port`.

This establishes our Port Forward rule, but if we created a firewall
policy it will likely block the traffic.

Firewall rules for Destination NAT
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is important to note that when creating firewall rules, the DNAT
translation occurs **before** traffic traverses the firewall. In other
words, the destination address has already been translated to
192.168.0.100.

So in our firewall ruleset, we want to allow traffic which previously matched
a destination nat rule. In order to avoid creating many rules, one for each
destination nat rule, we can accept all **'dnat'** connections with one simple
rule, using ``connection-status`` matcher:

.. code-block:: none

  set firewall ipv4 forward filter rule 10 action accept
  set firewall ipv4 forward filter rule 10 connection-status nat destination
  set firewall ipv4 forward filter rule 10 state new

This would generate the following configuration:

.. code-block:: none

  ipv4 {
      forward {
          filter {
              rule 10 {
                  action accept
                  connection-status {
                      nat destination
                  }
                  state new
              }
          }
      }
  }


1-to-1 NAT
----------

Another term often used for DNAT is **1-to-1 NAT**. For a 1-to-1 NAT
configuration, both DNAT and SNAT are used to NAT all traffic from an
external IP address to an internal IP address and vice-versa.

Typically, a 1-to-1 NAT rule omits the destination port (all ports) and
replaces the protocol with either **all** or **ip**.

Then a corresponding SNAT rule is created to NAT outgoing traffic for
the internal IP to a reserved external IP. This dedicates an external IP
address to an internal IP address and is useful for protocols which
don't have the notion of ports, such as GRE.

Here's an extract of a simple 1-to-1 NAT configuration with one internal
and one external interface:

.. code-block:: none

  set interfaces ethernet eth0 address '192.168.1.1/24'
  set interfaces ethernet eth0 description 'Inside interface'
  set interfaces ethernet eth1 address '192.0.2.30/24'
  set interfaces ethernet eth1 description 'Outside interface'
  set nat destination rule 2000 description '1-to-1 NAT example'
  set nat destination rule 2000 destination address '192.0.2.30'
  set nat destination rule 2000 inbound-interface name 'eth1'
  set nat destination rule 2000 translation address '192.168.1.10'
  set nat source rule 2000 description '1-to-1 NAT example'
  set nat source rule 2000 outbound-interface name 'eth1'
  set nat source rule 2000 source address '192.168.1.10'
  set nat source rule 2000 translation address '192.0.2.30'

Firewall rules are written as normal, using the internal IP address as
the source of outbound rules and the destination of inbound rules.

NAT before VPN
--------------

Some application service providers (ASPs) operate a VPN gateway to
provide access to their internal resources, and require that a
connecting organisation translate all traffic to the service provider
network to a source address provided by the ASP.

Load Balance
------------
Here we provide two examples on how to apply NAT Load Balance.

First scenario: apply destination NAT for all HTTP traffic comming through
interface eth0, and user 4 backends. First backend should received 30% of
the request, second backend should get 20%, third 15% and the fourth 35%
We will use source and destination address for hash generation.

.. code-block:: none

  set nat destination rule 10 inbound-interface name eth0
  set nat destination rule 10 protocol tcp
  set nat destination rule 10 destination port 80
  set nat destination rule 10 load-balance hash source-address
  set nat destination rule 10 load-balance hash destination-address
  set nat destination rule 10 load-balance backend 198.51.100.101 weight 30
  set nat destination rule 10 load-balance backend 198.51.100.102 weight 20
  set nat destination rule 10 load-balance backend 198.51.100.103 weight 15
  set nat destination rule 10 load-balance backend 198.51.100.104 weight 35

Second scenario: apply source NAT for all outgoing connections from
LAN 10.0.0.0/8, using 3 public addresses and equal distribution.
We will generate the hash randomly.

.. code-block:: none

  set nat source rule 10 outbound-interface name eth0
  set nat source rule 10 source address 10.0.0.0/8
  set nat source rule 10 load-balance hash random
  set nat source rule 10 load-balance backend 192.0.2.251 weight 33
  set nat source rule 10 load-balance backend 192.0.2.252 weight 33
  set nat source rule 10 load-balance backend 192.0.2.253 weight 34

Example Network
^^^^^^^^^^^^^^^

Here's one example of a network environment for an ASP.
The ASP requests that all connections from this company should come from
172.29.41.89 - an address that is assigned by the ASP and not in use at
the customer site.

.. figure:: /_static/images/nat_before_vpn_topology.*
   :scale: 100 %
   :alt: NAT before VPN Topology

   NAT before VPN Topology


Configuration
^^^^^^^^^^^^^

The required configuration can be broken down into 4 major pieces:

* A dummy interface for the provider-assigned IP;
* NAT (specifically, Source NAT);
* IPSec IKE and ESP Groups;
* IPSec VPN tunnels.


Dummy interface
"""""""""""""""

The dummy interface allows us to have an equivalent of the Cisco IOS
Loopback interface - a router-internal interface we can use for IP
addresses the router must know about, but which are not actually
assigned to a real network.

We only need a single step for this interface:

.. code-block:: none

  set interfaces dummy dum0 address '172.29.41.89/32'

NAT Configuration
"""""""""""""""""

.. code-block:: none

  set nat source rule 110 description 'Internal to ASP'
  set nat source rule 110 destination address '172.27.1.0/24'
  set nat source rule 110 source address '192.168.43.0/24'
  set nat source rule 110 translation address '172.29.41.89'
  set nat source rule 120 description 'Internal to ASP'
  set nat source rule 120 destination address '10.125.0.0/16'
  set nat source rule 120 source address '192.168.43.0/24'
  set nat source rule 120 translation address '172.29.41.89'

IPSec IKE and ESP
"""""""""""""""""

The ASP has documented their IPSec requirements:

* IKE Phase:

  * aes256 Encryption
  * sha256 Hashes

* ESP Phase:

  * aes256 Encryption
  * sha256 Hashes
  * DH Group 14


Additionally, we want to use VPNs only on our eth1 interface (the
external interface in the image above)

.. code-block:: none

  set vpn ipsec ike-group my-ike key-exchange 'ikev1'
  set vpn ipsec ike-group my-ike lifetime '7800'
  set vpn ipsec ike-group my-ike proposal 1 dh-group '14'
  set vpn ipsec ike-group my-ike proposal 1 encryption 'aes256'
  set vpn ipsec ike-group my-ike proposal 1 hash 'sha256'

  set vpn ipsec esp-group my-esp lifetime '3600'
  set vpn ipsec esp-group my-esp mode 'tunnel'
  set vpn ipsec esp-group my-esp pfs 'disable'
  set vpn ipsec esp-group my-esp proposal 1 encryption 'aes256'
  set vpn ipsec esp-group my-esp proposal 1 hash 'sha256'

  set vpn ipsec interface 'eth1'

IPSec VPN Tunnels
"""""""""""""""""

We'll use the IKE and ESP groups created above for this VPN. Because we
need access to 2 different subnets on the far side, we will need two
different tunnels. If you changed the names of the ESP group and IKE
group in the previous step, make sure you use the correct names here
too.

.. code-block:: none

  set vpn ipsec authentication psk vyos id '203.0.113.46'
  set vpn ipsec authentication psk vyos id '198.51.100.243'
  set vpn ipsec authentication psk vyos secret 'MYSECRETPASSWORD'
  set vpn ipsec site-to-site peer branch authentication local-id '203.0.113.46'
  set vpn ipsec site-to-site peer branch authentication mode 'pre-shared-secret'
  set vpn ipsec site-to-site peer branch authentication remote-id '198.51.100.243'
  set vpn ipsec site-to-site peer branch connection-type 'initiate'
  set vpn ipsec site-to-site peer branch default-esp-group 'my-esp'
  set vpn ipsec site-to-site peer branch ike-group 'my-ike'
  set vpn ipsec site-to-site peer branch ikev2-reauth 'inherit'
  set vpn ipsec site-to-site peer branch local-address '203.0.113.46'
  set vpn ipsec site-to-site peer branch remote-address '198.51.100.243'
  set vpn ipsec site-to-site peer branch tunnel 0 local prefix '172.29.41.89/32'
  set vpn ipsec site-to-site peer branch tunnel 0 remote prefix '172.27.1.0/24'
  set vpn ipsec site-to-site peer branch tunnel 1 local prefix '172.29.41.89/32'
  set vpn ipsec site-to-site peer branch tunnel 1 remote prefix '10.125.0.0/16'

Testing and Validation
""""""""""""""""""""""

If you've completed all the above steps you no doubt want to see if it's
all working.

Start by checking for IPSec SAs (Security Associations) with:

.. code-block:: none

  $ show vpn ipsec sa

  Peer ID / IP                            Local ID / IP
  ------------                            -------------
  198.51.100.243                          203.0.113.46

      Tunnel  State  Bytes Out/In   Encrypt  Hash    NAT-T  A-Time  L-Time  Proto
      ------  -----  -------------  -------  ----    -----  ------  ------  -----
      0       up     0.0/0.0        aes256   sha256  no     1647    3600    all
      1       up     0.0/0.0        aes256   sha256  no     865     3600    all

That looks good - we defined 2 tunnels and they're both up and running.
