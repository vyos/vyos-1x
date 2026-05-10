.. _cgnat:

#####
CGNAT
#####

:abbr:`CGNAT (Carrier-Grade Network Address Translation)` , also known as
Large-Scale NAT (LSN), is a type of network address translation used by
Internet Service Providers (ISPs) to enable multiple private IP addresses to
share a single public IP address. This technique helps to conserve the limited
IPv4 address space.
The 100.64.0.0/10 address block is reserved for use in carrier-grade NAT

Overview
========

CGNAT works by placing a NAT device within the ISP's network. This device
translates private IP addresses from customer networks to a limited pool of
public IP addresses assigned to the ISP. This allows many customers to share a
smaller number of public IP addresses.

Not all :rfc:`6888` requirements are implemented in CGNAT.

Implemented the following :rfc:`6888`  requirements:

- REQ 2: A CGN must have a default "IP address pooling" behavior of "Paired".
  CGN must use the same external IP address mapping for all sessions associated
  with the same internal IP address, be they TCP, UDP, ICMP, something else,
  or a mix of different protocols.
- REQ 3: The CGN function should not have any limitations on the size or the
  contiguity of the external address pool.
- REQ 4: A CGN must support limiting the number of external ports (or, 
  equivalently, "identifiers" for ICMP) that are assigned per subscriber

Advantages of CGNAT
-------------------

- **IPv4 Address Conservation**: CGNAT helps mitigate the exhaustion of IPv4 addresses by allowing multiple customers to share a single public IP address.
- **Scalability**: ISPs can support more customers without needing a proportional increase in public IP addresses.
- **Cost-Effective**: Reduces the cost associated with acquiring additional public IPv4 addresses.

Considerations
--------------

- **Traceability Issues**: Since multiple users share the same public IP address, tracking individual users for security and legal purposes can be challenging.
- **Performance Overheads**: The translation process can introduce latency and potential performance bottlenecks, especially under high load.
- **Application Compatibility**: Some applications and protocols may not work well with CGNAT due to their reliance on unique public IP addresses.
- **Port Allocation Limits**: Each public IP address has a limited number of ports, which can be exhausted, affecting the ability to establish new connections.
- **Port Control Protocol**: PCP is not implemented.

Port calculation
================

When implementing CGNAT, ensuring that there are enough ports allocated per subscriber is critical. Below is a summary based on RFC 6888.

1. **Total Ports Available**:

   - Total Ports: 65536 (0 to 65535)
   - Reserved Ports: Assume 1024 ports are reserved for well-known services and administrative purposes.
   - Usable Ports: 65536 - 1024 = 64512

2. **Estimate Ports Needed per Subscriber**:

   - Example: A household might need 1000 ports to ensure smooth operation for multiple devices and applications.

3. **Calculate the Number of Subscribers per Public IP**:

   - Usable Ports / Ports per Subscriber
   - 64512 / 1000 ≈ 64 subscribers per public IP


Configuration
=============

.. cfgcmd:: set nat cgnat pool external <pool-name> external-port-range <port-range>

    Set an external port-range for the external pool, the default range is 
    1024-65535. Multiple entries can be added to the same pool.

.. cfgcmd:: set nat cgnat pool external <pool-name> per-user-limit port <num>

    Set external source port limits that will be allocated to each subscriber
    individually. The default value is 2000.

.. cfgcmd:: set nat cgnat pool external <pool-name> range [address | address range | network] [seq]

    Set the range of external IP addresses for the CGNAT pool.
    The sequence is optional; if set, a lower value means higher priority.

.. cfgcmd:: set nat cgnat pool internal <pool-name> range [address range | network]

    Set the range of internal IP addresses for the CGNAT pool.

.. cfgcmd:: set nat cgnat rule <num> source pool <internal-pool-name>

    Set the rule for the source pool.

.. cfgcmd:: set nat cgnat rule <num> translation pool <external-pool-name>

    Set the rule for the translation pool.

.. cfgcmd:: set nat cgnat log-allocation

    Enable logging of IP address and ports allocations.


Configuration Examples
======================

Single external address
-----------------------

Example of setting up a basic CGNAT configuration:
In the following example, we define an external pool named `ext-1` with one external IP address


Each subscriber will be allocated a maximum of 2000 ports from the external pool.

.. code-block:: none

   set nat cgnat pool external ext1 external-port-range '1024-65535'
   set nat cgnat pool external ext1 per-user-limit port '2000'
   set nat cgnat pool external ext1 range '192.0.2.222/32'
   set nat cgnat pool internal int1 range '100.64.0.0/28'
   set nat cgnat rule 10 source pool 'int1'
   set nat cgnat rule 10 translation pool 'ext1'

Multiple external addresses
---------------------------

.. code-block:: none

   set nat cgnat pool external ext1 external-port-range '1024-65535'
   set nat cgnat pool external ext1 per-user-limit port '8000'
   set nat cgnat pool external ext1 range '192.0.2.1-192.0.2.2'
   set nat cgnat pool external ext1 range '203.0.113.253-203.0.113.254'
   set nat cgnat pool internal int1 range '100.64.0.1-100.64.0.32'
   set nat cgnat rule 10 source pool 'int1'
   set nat cgnat rule 10 translation pool 'ext1'

External address sequences
-----------------------------------

.. code-block:: none

   set nat cgnat pool external ext-01 per-user-limit port '16000'
   set nat cgnat pool external ext-01 range 203.0.113.1/32 seq '10'
   set nat cgnat pool external ext-01 range 192.0.2.1/32 seq '20'
   set nat cgnat pool internal int-01 range '100.64.0.0/29'
   set nat cgnat rule 10 source pool 'int-01'
   set nat cgnat rule 10 translation pool 'ext-01'


Operation commands
==================

.. opcmd:: show nat cgnat allocation

    Show address and port allocations

.. opcmd:: show nat cgnat allocation external-address <address>

    Show all allocations for an external IP address

.. opcmd:: show nat cgnat allocation internal-address <address>

    Show all allocations for an internal IP address

Show CGNAT allocations
----------------------

.. code-block:: none

   vyos@vyos:~$ show nat cgnat allocation
   Internal IP    External IP    Port range
   -------------  -------------  ------------
   100.64.0.0     203.0.113.1    1024-17023
   100.64.0.1     203.0.113.1    17024-33023
   100.64.0.2     203.0.113.1    33024-49023
   100.64.0.3     203.0.113.1    49024-65023
   100.64.0.4     192.0.2.1      1024-17023
   100.64.0.5     192.0.2.1      17024-33023
   100.64.0.6     192.0.2.1      33024-49023
   100.64.0.7     192.0.2.1      49024-65023

   vyos@vyos:~$ show nat cgnat allocation internal-address 100.64.0.4
   Internal IP    External IP    Port range
   -------------  -------------  ------------
   100.64.0.4     192.0.2.1      1024-17023


Further Reading
===============

- :rfc:`6598` - IANA-Reserved IPv4 Prefix for Shared Address Space
- :rfc:`6888` - Requirements for CGNAT
