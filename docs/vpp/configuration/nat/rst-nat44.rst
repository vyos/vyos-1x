:lastproofread: 2026-03-05

.. _vpp_config_nat_nat44:

.. include:: /_include/need_improvement.txt

#######################
VPP NAT44 Configuration
#######################

NAT44 has two main use cases:

* **Source NAT (SNAT)**: Enabling internet access for hosts in private
  networks using dynamic or static address translation.
* **Destination NAT (DNAT)**: Providing external access to internal services
  through static port forwarding rules.

VyOS supports both dynamic translation using address pools and static
mappings for predictable address translation requirements.

Configuring NAT44 involves a few steps:

1. Define the inside and outside interfaces.
2. Create NAT rules for SNAT or DNAT.

Dynamic and Static Operations
=============================

NAT44 configuration can be done in one of two ways or in both ways
simultaneously:

1. Dynamically performing NAT using a pool of public IP addresses.
2. Statically mapping private IP addresses to public IP addresses.

To configure dynamic NAT, you need to define a pool of public IP
addresses that will be used for translation. This offers an easy way to
provide internet access to internal users.

Static rules are suitable for scenarios where you need consistent and
predictable mappings between private and public IP addresses. They are also
the only way to configure DNAT.

NAT Rule Processing and Traffic Flow
------------------------------------

This section explains how different combinations of NAT rules affect
traffic handling on a router. There are three possible combinations of NAT
rule configurations:

1. **Dynamic NAT Only**

   * **All** traffic received on the "in" interface is processed by
     dynamic NAT rules without exceptions.

2. **Dynamic + Static NAT**

   * **All** traffic received on the "in" interface is first matched
     against static NAT rules.
   * If no match is found, it is then processed against dynamic NAT rules.

3. **Static NAT Only**

   * **All** traffic on the "in" interface is checked against static NAT
     rules.
   * If no match is found, the traffic is routed **without NAT**.

.. important::

   * If **dynamic NAT rules** are present, **all** traffic received on
     "in" interfaces is subject to NAT processing.
   * If **only static NAT rules** are configured, traffic that does not
     match any static rule is routed unchanged.

Interfaces Configuration
========================

The first step in configuring NAT44 is defining which interfaces handle
inside (private) and outside (public) traffic. VyOS uses these interface
designations to determine the direction of translation.

Inside Interfaces
-----------------

Inside interfaces connect to private networks where hosts need source NAT
to access external networks.

.. cfgcmd::

   set vpp nat nat44 interface inside <inside-interface>

Traffic flowing **from** inside interfaces gets source NAT applied,
translating private source addresses to public addresses from the
translation pool.

Outside Interfaces
------------------

Outside interfaces connect to public networks where external hosts may
need to access internal services.

.. cfgcmd::

   set vpp nat nat44 interface outside <outside-interface>

Traffic flowing **to** outside interfaces can trigger destination NAT
based on static rules, allowing external access to internal services.

Interface Roles and Traffic Flow
--------------------------------

.. note::

   While VyOS uses "inside" and "outside" as established conventions,
   the technical definitions are:
   
   * **Inside interface**: Interface where traffic originates that needs
     source NAT (SNAT)
   * **Outside interface**: Interface where traffic originates that needs
     destination NAT (DNAT)
   
   In complex network topologies, the same physical interface can be
   configured as both inside and outside to handle bidirectional NAT
   scenarios.

**Traffic Processing:**

1. **Inside → Outside** (SNAT): Private hosts accessing external networks
2. **Outside → Inside** (DNAT): External hosts accessing internal services
   via static rules
3. **Dynamic NAT**: Created automatically for inside→outside traffic
4. **Static NAT**: Requires explicit configuration for outside→inside
   traffic

Multiple Interface Support
--------------------------

You can configure multiple interfaces as inside or outside to support
complex network topologies:

.. code-block:: none

   # Multiple inside interfaces (different private networks)
   set vpp nat nat44 interface inside eth0
   set vpp nat nat44 interface inside eth2
   
   # Multiple outside interfaces (redundancy or load balancing)  
   set vpp nat nat44 interface outside eth1
   set vpp nat nat44 interface outside eth3

Address Pool Configuration
==========================

Address pools define ranges of IP addresses that can be used for NAT
translations. VyOS NAT44 supports two types of address pools, each serving
different purposes.

Translation Pools
-----------------

Translation pools are used for dynamic source NAT (SNAT). They provide a
range of public IP addresses that can be dynamically assigned to private
hosts when they access external networks.

.. cfgcmd::

   set vpp nat nat44 address-pool translation address
   <ip-address | ip-address-range>

.. cfgcmd::

   set vpp nat nat44 address-pool translation interface <interface-name>

**Examples:**

.. code-block:: none

   # Single address pool
   set vpp nat nat44 address-pool translation address 203.0.113.10

   # Address range pool  
   set vpp nat nat44 address-pool translation address 203.0.113.10-203.0.113.20

   # Interface-based pool (use a first IP assigned to the interface)
   set vpp nat nat44 address-pool translation interface eth1

Twice-NAT Pools
---------------

Twice-NAT pools are used when performing both source and destination NAT on
the same traffic flow. This is particularly useful in scenarios where you
need to:

* Translate both source and destination addresses
* Provide access between networks with overlapping IP ranges
* Implement advanced NAT scenarios like self-twice-nat

.. cfgcmd::

   set vpp nat nat44 address-pool twice-nat address
   <ip-address | ip-address-range>

.. cfgcmd::

   set vpp nat nat44 address-pool twice-nat interface <interface-name>

**Examples:**

.. code-block:: none

   # Twice-NAT pool for advanced scenarios
   set vpp nat nat44 address-pool twice-nat address 192.168.100.1-192.168.100.10

   # Interface-based twice-nat pool
   set vpp nat nat44 address-pool twice-nat interface eth2

Pool Requirements
-----------------

.. important::

   * For dynamic NAT to work, you must configure at least one
     **translation** pool.
   * For static rules with twice-nat options, you must configure a
     **twice-nat** pool.
   * Interface-based pools automatically include main (first) IP address
     assigned to the specified interface.

Pool Selection Priority
-----------------------

When multiple pools are configured, VyOS uses the following selection
priority:

1. **Static mappings**: Always use the specific external address defined in
   the rule.
2. **Dynamic NAT**: Use available addresses from translation pools in the
   order they were configured.
3. **Twice-NAT**: Use addresses from twice-nat pools for secondary
   translation.

.. note::

    As soon as you have configured interfaces and pool, the NAT44 is
    operational.

Static Rules Configuration
==========================

Static NAT rules provide predictable and consistent mappings between private
and public IP addresses. They are essential for:

* **Destination NAT (DNAT)**: Allowing external hosts to access services in
  the private network.
* **Server publishing**: Making internal services available from the
  Internet.
* **Consistent mappings**: Ensuring the same private IP always maps to the
  same public IP.

Unlike dynamic NAT that uses a pool of addresses, static rules create
one-to-one mappings that persist until explicitly removed.

Basic Static Rule Configuration
-------------------------------

To create a static NAT rule, you need to define the local (internal) and
external (public) address mappings:

.. cfgcmd::

   set vpp nat nat44 static rule <rule-number> local address <internal-ip>

.. cfgcmd::

   set vpp nat nat44 static rule <rule-number> external address <external-ip>

Where:

* ``<rule-number>`` is a unique identifier for the rule
* ``<internal-ip>`` is the private IP address in your local network
* ``<external-ip>`` is the public IP address that external hosts will use

This basic configuration creates a static one-to-one mapping. Traffic from
outside to the external IP will be translated to the internal IP, and vice
versa.

Port-based Static Rules
-----------------------

For more granular control, you can create port-specific static rules. This
is useful when you want to publish specific services:

.. cfgcmd::

   set vpp nat nat44 static rule <rule-number> local address <internal-ip>

.. cfgcmd::

   set vpp nat nat44 static rule <rule-number> local port <internal-port>

.. cfgcmd::

   set vpp nat nat44 static rule <rule-number> external address <external-ip>

.. cfgcmd::

   set vpp nat nat44 static rule <rule-number> external port <external-port>

.. cfgcmd::

   set vpp nat nat44 static rule <rule-number> protocol <protocol>

Where:

* ``<internal-port>`` and ``<external-port>`` are the port numbers used by
  the connection.
* ``<protocol>`` specifies the protocol (tcp, udp, icmp).

.. important::

   If you do not specify ports and protocol, the rule will apply to *all*
   traffic between the specified internal and external addresses.

   Rules must contain either both ports and protocol, or neither.

Advanced Static Rule Options
----------------------------

VyOS NAT44 supports several advanced options for static rules:

Twice-NAT
^^^^^^^^^

Twice-NAT performs both source and destination NAT. When an external host
accesses an internal service, the source IP of such a connection is
translated to an address from the twice-NAT address pool.

This is practical in scenarios where internal services cannot connect to
public networks, so they see such traffic as internal.

The twice-NAT option can be enabled with the following command:

.. cfgcmd::

   set vpp nat nat44 static rule <rule-number> options twice-nat

Self Twice-NAT
^^^^^^^^^^^^^^

Self Twice-NAT is used when a local host needs to access itself via the
external address:

.. cfgcmd::

   set vpp nat nat44 static rule <rule-number> options self-twice-nat

This option rewrites source IP addresses on packets sent only from a local
address to an external address configured in a rule.

.. important::

   * Using ``self-twice-nat`` option requires you to set the interface
     connected to the local network as both inside and outside, because
     both source and destination NAT need to be applied.
   * External IP address used in static rules must belong to one of the
     configured translation pools.

Out-to-In Only
^^^^^^^^^^^^^^

Restricts the rule to only apply to traffic from outside to inside
interfaces:

.. cfgcmd::

   set vpp nat nat44 static rule <rule-number> options out-to-in-only

This prevents the creation of sessions from the inside interface, making it
a purely DNAT rule.

Force Twice-NAT Address
^^^^^^^^^^^^^^^^^^^^^^^

When using twice-nat, you can force the use of a specific IP address from
the twice-nat address pool:

.. cfgcmd::

   set vpp nat nat44 static rule <rule-number> options twice-nat-address
   <ip-address>

Rule Description
^^^^^^^^^^^^^^^^

To document your rules, you can add a description:

.. cfgcmd::

   set vpp nat nat44 static rule <rule-number> description <description>

Static Rules Configuration Examples
-----------------------------------

**Full one-to-one NAT mapping:**

.. code-block:: none

   set vpp nat nat44 static rule 100 local address 192.168.1.10
   set vpp nat nat44 static rule 100 external address 203.0.113.10
   set vpp nat nat44 static rule 100 description "One-to-one mapping"

**Port-specific SSH access:**

.. code-block:: none

   set vpp nat nat44 static rule 200 local address 192.168.1.20
   set vpp nat nat44 static rule 200 local port 22
   set vpp nat nat44 static rule 200 external address 203.0.113.10
   set vpp nat nat44 static rule 200 external port 2222
   set vpp nat nat44 static rule 200 protocol tcp
   set vpp nat nat44 static rule 200 description "SSH access to server"

**Twice-NAT for local service access:**

.. code-block:: none

   set vpp nat nat44 static rule 300 local address 192.168.1.30
   set vpp nat nat44 static rule 300 local port 80
   set vpp nat nat44 static rule 300 external address 203.0.113.10
   set vpp nat nat44 static rule 300 external port 80
   set vpp nat nat44 static rule 300 protocol tcp
   set vpp nat nat44 static rule 300 options twice-nat
   set vpp nat nat44 static rule 300 description "Web service with twice-nat"

.. note::

   When using twice-nat or self-twice-nat options, ensure you have
   configured a twice-nat address pool using:
   
   ``set vpp nat nat44 address-pool twice-nat address <twice-nat-ip-range>``

Exclude Rules Configuration
===========================

Exclude rules allow you to prevent specific traffic from undergoing NAT
translation. This is particularly useful for:

* **Router management**: Allowing SSH access to the router itself from
  external networks.
* **Service bypass**: Excluding specific services from NAT processing
* **Traffic forwarding**: Allowing forwarded traffic to bypass NAT with 1-to-1
  mapping.

Exclude rules take precedence over both dynamic and static NAT rules,
ensuring that matching traffic bypasses NAT processing. For forwarded
traffic, exclude rules create invisible 1-to-1 mappings that allow packets
to pass through without NAT modifications.

Basic Exclude Rule Configuration
--------------------------------

To create an exclude rule, you need to specify the traffic characteristics
that should bypass NAT. You can configure exclude rules in two ways:

**Option 1: Using local address**

.. cfgcmd::

   set vpp nat nat44 exclude rule <rule-number> local-address <internal-ip>

**Option 2: Using external interface**

.. cfgcmd::

   set vpp nat nat44 exclude rule <rule-number> external-interface
   <interface-name>

Where:

* ``<rule-number>`` is a unique identifier for the exclude rule.
* ``<internal-ip>`` is the local IP address that should be excluded from
   NAT.
* ``<interface-name>`` is the external interface where the traffic
     originates.

.. important::

   You must use either ``local-address`` OR ``external-interface`` in an
   exclude rule, but not both simultaneously. These options are mutually
   exclusive.

Port-specific Exclude Rules
---------------------------

For more granular control, you can exclude only specific ports and protocols.
You can combine port and protocol specifications with either ``local-address`` or
``external-interface``:

**With local address:**

.. cfgcmd::

   set vpp nat nat44 exclude rule <rule-number> local-address <internal-ip>

.. cfgcmd::

   set vpp nat nat44 exclude rule <rule-number> local-port <port-number>

.. cfgcmd::

   set vpp nat nat44 exclude rule <rule-number> protocol <protocol>

**With external interface:**

.. cfgcmd::

   set vpp nat nat44 exclude rule <rule-number> external-interface
   <interface-name>

.. cfgcmd::

   set vpp nat nat44 exclude rule <rule-number> local-port <port-number>

.. cfgcmd::

   set vpp nat nat44 exclude rule <rule-number> protocol <protocol>

Where:

* ``<port-number>`` is the specific port to exclude (1-65535)
* ``<protocol>`` can be ``tcp``, ``udp``, ``icmp``, or ``all`` (default)

Rule Documentation
------------------

Add descriptions to your exclude rules for better management:

.. cfgcmd::

   set vpp nat nat44 exclude rule <rule-number> description <description>

Exclude Rules Configuration Examples
------------------------------------

**Exclude SSH access to router:**

.. code-block:: none

   # Allow external SSH access to router without NAT
   set vpp nat nat44 exclude rule 10 local-address 192.168.1.1
   set vpp nat nat44 exclude rule 10 local-port 22
   set vpp nat nat44 exclude rule 10 protocol tcp
   set vpp nat nat44 exclude rule 10 description "SSH access to router"

**Exclude SNMP monitoring:**

.. code-block:: none

   # Allow SNMP monitoring without NAT translation
   set vpp nat nat44 exclude rule 20 local-port 161
   set vpp nat nat44 exclude rule 20 protocol udp
   set vpp nat nat44 exclude rule 20 external-interface eth1
   set vpp nat nat44 exclude rule 20 description "SNMP monitoring"

**Exclude all traffic to router management interface:**

.. code-block:: none

   # Exclude all traffic to router's management IP
   set vpp nat nat44 exclude rule 30 local-address 192.168.100.1
   set vpp nat nat44 exclude rule 30 description "Management interface bypass"

**Exclude all traffic from external interface:**

.. code-block:: none

   # Exclude all traffic from external interface (alternative approach)
   set vpp nat nat44 exclude rule 31 external-interface eth1
   set vpp nat nat44 exclude rule 31 description "External interface bypass"

**Exclude forwarded traffic for specific service:**

.. code-block:: none

   # Allow external access to internal server without NAT translation
   set vpp nat nat44 exclude rule 40 local-address 192.168.1.50
   set vpp nat nat44 exclude rule 40 local-port 8080
   set vpp nat nat44 exclude rule 40 protocol tcp
   set vpp nat nat44 exclude rule 40 description "Direct access to internal service"

Common Use Cases
----------------

**Router Administration:**

Exclude rules are essential when you need to manage the router from external
networks. Without exclude rules, NAT would attempt to translate the router's
own traffic, potentially breaking management connections.

**Service Monitoring:**

Network monitoring systems often need direct access to router services.
Exclude rules ensure that monitoring traffic bypasses NAT translation.

**Routing Protocols:**

Some routing protocols or network services may require direct communication
without NAT interference.

**Traffic Forwarding:**

Exclude rules also work for forwarded traffic between networks. Without
exclude rules, traffic from external to local networks must either match a
static rule or be dropped. With exclude rules, traffic can bypass NAT
processing with invisible 1-to-1 mappings.

.. important::

   Exclude rules affect both traffic destined for the router itself and
   forwarded traffic flowing through the router. For forwarded traffic, exclude
   rules create transparent 1-to-1 mappings that allow packets to pass without
   NAT modifications, while from the outside perspective, the traffic appears to
   bypass NAT entirely.

Advanced NAT44 Settings
=======================

VyOS provides additional NAT44 settings for fine-tuning performance and
behavior.

Session Timeouts
----------------

NAT44 maintains translation sessions with configurable timeout values for
different protocols:

.. cfgcmd:: set vpp nat nat44 timeout icmp <seconds>

   Set the timeout for ICMP sessions (Default: 60 seconds).

.. cfgcmd:: set vpp nat nat44 timeout tcp-established <seconds>

   Set the timeout for established TCP connections (Default: 7440 seconds
   or 2 hours 4 minutes).

.. cfgcmd:: set vpp nat nat44 timeout tcp-transitory <seconds>

   Set the timeout for transitory TCP connections (setup/teardown) (Default:
   240 seconds or 4 minutes).

.. cfgcmd:: set vpp nat nat44 timeout udp <seconds>

   Set the timeout for UDP sessions (Default: 300 seconds or 5 minutes).

**Example:**

.. code-block:: none

   # Customize timeouts for high-traffic environment
   set vpp nat nat44 timeout tcp-established 3600
   set vpp nat nat44 timeout udp 600
   set vpp nat nat44 timeout icmp 30

Session Limits
--------------

Control the maximum number of concurrent NAT sessions:

.. cfgcmd:: set vpp nat nat44 session-limit <number>

   Set the maximum number of NAT sessions per worker thread (Default:
   64512).

This setting helps prevent memory exhaustion and ensures predictable
performance under high load.

**Example:**

.. code-block:: none

   # Increase session limit for high-capacity deployment
   set vpp nat nat44 session-limit 100000

Complete Configuration Example
==============================

Here's a complete example showing how to configure VyOS NAT44 for a typical
network setup:

**Network Topology:**

.. code-block:: none

   Internet (203.0.113.0/24)
           |
   ┌───────────────────┐
   │   eth1 (outside)  │ 203.0.113.1/24
   │     VyOS Router   │
   │   eth0 (inside)   │ 192.168.1.1/24  
   └───────────────────┘
           |
   Internal Network (192.168.1.0/24)
   ├── 192.168.1.10 (Web Server)
   ├── 192.168.1.20 (SSH Server)  
   └── 192.168.1.30 (API Service)

**Configuration:**

.. code-block:: none

   # Configure interfaces
   set vpp nat nat44 interface inside eth0
   set vpp nat nat44 interface outside eth1

   # Configure address pools
   set vpp nat nat44 address-pool translation address 203.0.113.10-203.0.113.50
   set vpp nat nat44 address-pool twice-nat address 203.0.113.100-203.0.113.110

   # Exclude rules for router management
   set vpp nat nat44 exclude rule 10 local-address 203.0.113.1
   set vpp nat nat44 exclude rule 10 local-port 22
   set vpp nat nat44 exclude rule 10 protocol tcp
   set vpp nat nat44 exclude rule 10 description "SSH access to router"

   set vpp nat nat44 exclude rule 11 local-address 203.0.113.1
   set vpp nat nat44 exclude rule 11 local-port 443
   set vpp nat nat44 exclude rule 11 protocol tcp
   set vpp nat nat44 exclude rule 11 description "HTTPS access to router web interface"

   # Static rule for web server (HTTP)
   set vpp nat nat44 static rule 100 local address 192.168.1.10
   set vpp nat nat44 static rule 100 local port 80
   set vpp nat nat44 static rule 100 external address 203.0.113.10
   set vpp nat nat44 static rule 100 external port 80
   set vpp nat nat44 static rule 100 protocol tcp
   set vpp nat nat44 static rule 100 description "Public web server"

   # Static rule for web server (HTTPS)
   set vpp nat nat44 static rule 101 local address 192.168.1.10
   set vpp nat nat44 static rule 101 local port 443
   set vpp nat nat44 static rule 101 external address 203.0.113.10
   set vpp nat nat44 static rule 101 external port 443
   set vpp nat nat44 static rule 101 protocol tcp
   set vpp nat nat44 static rule 101 description "Public web server HTTPS"

   # Static rule for SSH server with custom port
   set vpp nat nat44 static rule 200 local address 192.168.1.20
   set vpp nat nat44 static rule 200 local port 22
   set vpp nat nat44 static rule 200 external address 203.0.113.11
   set vpp nat nat44 static rule 200 external port 2222
   set vpp nat nat44 static rule 200 protocol tcp
   set vpp nat nat44 static rule 200 description "SSH access"

   # Static rule for API service (out-to-in only for security)
   set vpp nat nat44 static rule 300 local address 192.168.1.30
   set vpp nat nat44 static rule 300 local port 8080
   set vpp nat nat44 static rule 300 external address 203.0.113.12
   set vpp nat nat44 static rule 300 external port 8080
   set vpp nat nat44 static rule 300 protocol tcp
   set vpp nat nat44 static rule 300 options out-to-in-only
   set vpp nat nat44 static rule 300 description "API service (No Internet access for it)"

Best Practices and Troubleshooting
==================================

Recommendations
---------------

* **Use exclude rules** for router management services like SSH
* **Use out-to-in-only** for services that do not need access to external
   networks.
* **Limit port ranges** in static rules to only necessary ports.
* **Document all rules** using descriptions for easier management.
* **Use non-standard ports** for publishing SSH and other administrative
   services.
* **Configure appropriate pool sizes** based on expected concurrent
   connections in your network.

Common Configuration Issues
---------------------------

**Static rules not working:**

1. Verify that the external IP address is included in an address pool
2. Check that interfaces are correctly configured as inside or outside
3. Ensure firewall rules allow the traffic

**Twice-NAT not functioning:**

1. Confirm twice-nat pool is configured
2. Verify static rules have the correct twice-nat option
3. Check that both translation and twice-nat pools are properly defined

**Router management access issues:**

1. Verify exclude rules are configured for management services
2. Check that local-address matches the router's interface IP
3. Ensure external-interface is correctly specified

**Forwarded traffic from external networks not bypassing NAT:**

1. Verify exclude rules are configured for the specific traffic flow
2. Check that local-address matches the destination IP in the internal
   network
3. Ensure protocol and port specifications match the traffic requirements

Operational Commands
====================

Monitor NAT44 status and active connections using VyOS operational
commands:

.. opcmd:: show vpp nat nat44 addresses

   Display configured NAT44 address pools.

.. opcmd:: show vpp nat nat44 interfaces

   Show which interfaces are configured as inside or outside for NAT44.

.. opcmd:: show vpp nat nat44 sessions

   Display active NAT44 translation sessions.

.. opcmd:: show vpp nat nat44 static

   Show all configured static NAT mappings.

.. opcmd:: show vpp nat nat44 summary

   Display a summary of NAT44 and statistics.
