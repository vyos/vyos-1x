:lastproofread: 2025-09-04

.. _vpp_config_acl:

.. include:: /_include/need_improvement.txt

#####################
VPP ACL Configuration
#####################

VPP ACLs (Access Control Lists) provide a way to filter traffic passing through VPP interfaces. They offer a high-performance packet filtering solution that can be used as a fast firewall alternative.

VyOS VPP ACL implementation supports two main types of access control lists:

* **IP ACLs** - Layer 3 filtering based on IPv4/IPv6 addresses, ports, and protocols (can be applied to both input and output directions)
* **MAC ACLs** - Layer 2 filtering based on MAC addresses and IP prefixes (can only be applied to input direction)

Structure and Components
========================

Tags
----

ACL tags are named rule sets that contain one or more access control entries (ACEs). Tags provide a way to group related rules and apply them consistently across different interfaces.

- Tag names are user-defined text strings
- Each tag can contain multiple numbered rules
- Tags can be applied to interfaces in input or output direction
- Multiple tags can be applied to a single interface

Interface Application
---------------------

ACL tags are applied to interfaces to control traffic flow:

- **Input direction**: Filters traffic entering the interface
- **Output direction**: Filters traffic leaving the interface

.. note::
   **Important Limitation**: MAC ACLs can only be applied to the input direction of interfaces. They cannot filter outbound traffic. Use IP ACLs if you need to filter traffic in both directions.

Rule Processing
---------------

Rules within an ACL are processed in numerical order (lowest to highest). The first matching rule determines the action taken on the packet.

Available actions:

- ``permit`` - Allow the packet to continue
- ``deny`` - Drop the packet
- ``permit-reflect`` - Allow traffic and automatically permit return traffic

L3/IP ACLs
==========

IP ACLs provide Layer 3 filtering capabilities based on IPv4 and IPv6 addresses, port numbers, and protocols. They support both stateless and stateful (reflexive) filtering.

Creating IP ACL Tags
--------------------

IP ACL tags are created under the ``vpp acl ip`` configuration node:

.. code-block:: none

   set vpp acl ip tag-name <tag-name>
   set vpp acl ip tag-name <tag-name> description '<description>'

Example:

.. code-block:: none

   set vpp acl ip tag-name 'WEB-FILTER'
   set vpp acl ip tag-name 'WEB-FILTER' description 'Web server access control'

Adding Rules to IP ACL Tags
---------------------------

Rules are added to IP ACL tags with specific rule numbers:

.. code-block:: none

   set vpp acl ip tag-name <tag-name> rule <rule-number>

Basic IP ACL Rule Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each rule requires an action and matching criteria:

.. code-block:: none

   set vpp acl ip tag-name <tag-name> rule <rule-number> action <permit|deny|permit-reflect>
   set vpp acl ip tag-name <tag-name> rule <rule-number> description '<description>'
   set vpp acl ip tag-name <tag-name> rule <rule-number> protocol <protocol>

**Actions:**

- ``permit`` - Allow matching traffic
- ``deny`` - Block matching traffic  
- ``permit-reflect`` - Allow outbound traffic and automatically permit return traffic

**Protocols:**

- ``all`` - Match all IP protocols (default)
- Or specific protocol by name, e.g. ``tcp``, ``udp``, ``icmp``

Source and Destination Matching
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Configure source and destination parameters:

.. code-block:: none

   # Source configuration
   set vpp acl ip tag-name <tag-name> rule <rule-number> source prefix <ip-prefix>
   set vpp acl ip tag-name <tag-name> rule <rule-number> source port <port-spec>

   # Destination configuration  
   set vpp acl ip tag-name <tag-name> rule <rule-number> destination prefix <ip-prefix>
   set vpp acl ip tag-name <tag-name> rule <rule-number> destination port <port-spec>

**Prefix Specification:**

- ``<x.x.x.x/x>`` - IPv4 prefix in CIDR notation
- ``<h:h:h:h:h:h:h:h/x>`` - IPv6 prefix in CIDR notation

**Port Specification:**

- ``<1-65535>`` - Single port number
- ``<start>-<end>`` - Port range (e.g., 1001-1005)

TCP Flags Matching
^^^^^^^^^^^^^^^^^^

For TCP protocol rules, you can match specific TCP flags:

.. code-block:: none

   # Match packets with specific flags set
   set vpp acl ip tag-name <tag-name> rule <rule-number> tcp-flags is-set <ack|cwr|ecn|fin|psh|rst|syn|urg>

   # Match packets without specific flags set
   set vpp acl ip tag-name <tag-name> rule <rule-number> tcp-flags is-not-set <ack|cwr|ecn|fin|psh|rst|syn|urg>

IP ACL Configuration Examples
-----------------------------

Example 1: Basic Web Server ACL
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

   # Create ACL for web server access
   set vpp acl ip tag-name 'WEB-SERVER'
   set vpp acl ip tag-name 'WEB-SERVER' description 'Web server access control'
   
   # Allow HTTP traffic
   set vpp acl ip tag-name 'WEB-SERVER' rule 10 action permit
   set vpp acl ip tag-name 'WEB-SERVER' rule 10 protocol tcp
   set vpp acl ip tag-name 'WEB-SERVER' rule 10 destination port 80
   
   # Allow HTTPS traffic
   set vpp acl ip tag-name 'WEB-SERVER' rule 20 action permit
   set vpp acl ip tag-name 'WEB-SERVER' rule 20 protocol tcp
   set vpp acl ip tag-name 'WEB-SERVER' rule 20 destination port 443
   
   # Deny all other traffic
   set vpp acl ip tag-name 'WEB-SERVER' rule 999 action deny
   set vpp acl ip tag-name 'WEB-SERVER' rule 999 protocol all

Example 2: Network Segmentation ACL
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

   # Create ACL for network segmentation
   set vpp acl ip tag-name 'DMZ-FILTER'
   set vpp acl ip tag-name 'DMZ-FILTER' description 'DMZ to internal network filter'
   
   # Allow specific internal subnet access
   set vpp acl ip tag-name 'DMZ-FILTER' rule 10 action permit
   set vpp acl ip tag-name 'DMZ-FILTER' rule 10 destination prefix '192.168.100.0/24'
   set vpp acl ip tag-name 'DMZ-FILTER' rule 10 protocol tcp
   set vpp acl ip tag-name 'DMZ-FILTER' rule 10 destination port 443
   
   # Allow DNS queries
   set vpp acl ip tag-name 'DMZ-FILTER' rule 20 action permit
   set vpp acl ip tag-name 'DMZ-FILTER' rule 20 destination prefix '192.168.1.10/32'
   set vpp acl ip tag-name 'DMZ-FILTER' rule 20 protocol udp
   set vpp acl ip tag-name 'DMZ-FILTER' rule 20 destination port 53
   
   # Block everything else to internal networks
   set vpp acl ip tag-name 'DMZ-FILTER' rule 100 action deny
   set vpp acl ip tag-name 'DMZ-FILTER' rule 100 destination prefix '192.168.0.0/16'

Example 3: Reflexive ACL
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

   # Create reflexive ACL for outbound connections
   set vpp acl ip tag-name 'OUTBOUND-REFLECT'
   set vpp acl ip tag-name 'OUTBOUND-REFLECT' description 'Allow outbound with return traffic'
   
   # Allow outbound HTTP/HTTPS with return traffic
   set vpp acl ip tag-name 'OUTBOUND-REFLECT' rule 10 action permit-reflect
   set vpp acl ip tag-name 'OUTBOUND-REFLECT' rule 10 protocol tcp
   set vpp acl ip tag-name 'OUTBOUND-REFLECT' rule 10 destination port 80
   
   set vpp acl ip tag-name 'OUTBOUND-REFLECT' rule 20 action permit-reflect
   set vpp acl ip tag-name 'OUTBOUND-REFLECT' rule 20 protocol tcp
   set vpp acl ip tag-name 'OUTBOUND-REFLECT' rule 20 destination port 443

Applying IP ACL Tags to Interfaces
----------------------------------

IP ACL tags are applied to interfaces using the interface configuration:

.. code-block:: none

   # Apply to input direction
   set vpp acl ip interface <interface> input acl-tag <number> tag-name <tag-name>
   
   # Apply to output direction  
   set vpp acl ip interface <interface> output acl-tag <number> tag-name <tag-name>

Where:

- ``<interface>`` - Interface name (e.g., eth0, eth1)
- ``<number>`` - ACL rule number (0-4294967295) for ordering multiple ACL tags
- ``<tag-name>`` - Name of the ACL tag to apply

Multiple tags can be applied to the same interface and direction by using different ACL rule numbers.

Example:

.. code-block:: none

   # Apply web server ACL to input direction
   set vpp acl ip interface eth0 input acl-tag 10 tag-name 'WEB-SERVER'
   
   # Apply outbound reflexive ACL to output direction
   set vpp acl ip interface eth1 output acl-tag 10 tag-name 'OUTBOUND-REFLECT'
   
   # Apply multiple ACLs to the same interface and direction
   set vpp acl ip interface eth0 input acl-tag 20 tag-name 'FIREWALL'

L2/MAC ACLs  
===========

MAC ACLs provide Layer 2 filtering capabilities based on MAC addresses and IP prefixes. They are particularly useful for controlling access at the data link layer.

.. important::
   **Direction Limitation**: MAC ACLs can **only** be applied to the **input direction** of interfaces. They cannot filter outbound/output traffic. If you need bidirectional filtering, use IP ACLs instead.

Creating MAC ACL Tags
-----------------------

MAC ACL tags are created under the ``vpp acl mac`` configuration node:

.. code-block:: none

   set vpp acl mac tag-name <tag-name>
   set vpp acl mac tag-name <tag-name> description '<description>'

Example:

.. code-block:: none

   set vpp acl mac tag-name 'MAC-FILTER'
   set vpp acl mac tag-name 'MAC-FILTER' description 'Layer 2 MAC address filtering'

Adding Rules to MAC ACL Tags
------------------------------

Rules are added to MAC ACL tags with specific rule numbers:

.. code-block:: none

   set vpp acl mac tag-name <tag-name> rule <rule-number>

Basic MAC ACL Rule Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each rule requires an action and matching criteria:

.. code-block:: none

   set vpp acl mac tag-name <tag-name> rule <rule-number> action <permit|deny>
   set vpp acl mac tag-name <tag-name> rule <rule-number> description '<description>'

**Actions:**

- ``permit`` - Allow matching traffic
- ``deny`` - Block matching traffic

Note: MAC ACLs do not support the ``permit-reflect`` action available in IP ACLs.

MAC Address Matching
^^^^^^^^^^^^^^^^^^^^

Configure MAC address matching criteria:

.. code-block:: none

   set vpp acl mac tag-name <tag-name> rule <rule-number> mac-address <mac-address>
   set vpp acl mac tag-name <tag-name> rule <rule-number> mac-mask <mac-mask>

**MAC Address Specification:**

- ``mac-address`` - Source MAC address to match (format: xx:xx:xx:xx:xx:xx)
- ``mac-mask`` - MAC address mask (default: ff:ff:ff:ff:ff:ff for exact match)

The MAC mask allows for partial MAC address matching. For example:
- ``ff:ff:ff:00:00:00`` matches the first 3 octets (OUI)
- ``ff:ff:ff:ff:ff:ff`` matches the complete MAC address (default)

IP Prefix Matching
^^^^^^^^^^^^^^^^^^

Configure IP prefix matching for the source:

.. code-block:: none

   set vpp acl mac tag-name <tag-name> rule <rule-number> prefix <ip-prefix>

**Prefix Specification:**

- Supports both IPv4 and IPv6 prefixes in CIDR notation
- Examples: ``192.168.1.0/24``, ``10.0.0.0/8``, ``2001:db8::/32``

MAC ACL Configuration Examples
--------------------------------

Example 1: Device Whitelist
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

   # Create MAC ACL for device whitelisting
   set vpp acl mac tag-name 'DEVICE-WHITELIST'
   set vpp acl mac tag-name 'DEVICE-WHITELIST' description 'Allow only approved devices'
   
   # Allow specific workstation
   set vpp acl mac tag-name 'DEVICE-WHITELIST' rule 10 action permit
   set vpp acl mac tag-name 'DEVICE-WHITELIST' rule 10 mac-address '00:1b:21:12:34:56'
   set vpp acl mac tag-name 'DEVICE-WHITELIST' rule 10 prefix '192.168.1.100/32'
   set vpp acl mac tag-name 'DEVICE-WHITELIST' rule 10 description 'Admin workstation'
   
   # Allow specific server
   set vpp acl mac tag-name 'DEVICE-WHITELIST' rule 20 action permit
   set vpp acl mac tag-name 'DEVICE-WHITELIST' rule 20 mac-address '00:1b:21:78:90:ab'
   set vpp acl mac tag-name 'DEVICE-WHITELIST' rule 20 prefix '192.168.1.10/32'
   set vpp acl mac tag-name 'DEVICE-WHITELIST' rule 20 description 'Web server'
   
   # Deny everything else
   set vpp acl mac tag-name 'DEVICE-WHITELIST' rule 999 action deny
   set vpp acl mac tag-name 'DEVICE-WHITELIST' rule 999 mac-address '00:00:00:00:00:00'
   set vpp acl mac tag-name 'DEVICE-WHITELIST' rule 999 mac-mask '00:00:00:00:00:00'

Example 2: Vendor-Based Filtering
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

   # Create MAC ACL for vendor-based filtering
   set vpp acl mac tag-name 'VENDOR-FILTER'
   set vpp acl mac tag-name 'VENDOR-FILTER' description 'Filter by MAC vendor OUI'
   
   # Deny Realtek devices (OUI: 00:e0:4c)
   set vpp acl mac tag-name 'VENDOR-FILTER' rule 10 action deny
   set vpp acl mac tag-name 'VENDOR-FILTER' rule 10 mac-address '00:e0:4c:00:00:00'
   set vpp acl mac tag-name 'VENDOR-FILTER' rule 10 mac-mask 'ff:ff:ff:00:00:00'
   set vpp acl mac tag-name 'VENDOR-FILTER' rule 10 description 'Block Realtek devices'
   
   # Allow all other devices
   set vpp acl mac tag-name 'VENDOR-FILTER' rule 100 action permit
   set vpp acl mac tag-name 'VENDOR-FILTER' rule 100 mac-address '00:00:00:00:00:00'
   set vpp acl mac tag-name 'VENDOR-FILTER' rule 100 mac-mask '00:00:00:00:00:00'
   set vpp acl mac tag-name 'VENDOR-FILTER' rule 100 description 'Allow all other vendors'

Example 3: Network Segmentation by MAC
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

   # Create MAC ACL for network segmentation
   set vpp acl mac tag-name 'SEGMENT-FILTER'
   set vpp acl mac tag-name 'SEGMENT-FILTER' description 'Segment networks by MAC/IP binding'
   
   # Allow management VLAN devices
   set vpp acl mac tag-name 'SEGMENT-FILTER' rule 10 action permit
   set vpp acl mac tag-name 'SEGMENT-FILTER' rule 10 mac-address '02:01:00:00:00:00'
   set vpp acl mac tag-name 'SEGMENT-FILTER' rule 10 mac-mask 'ff:ff:00:00:00:00'
   set vpp acl mac tag-name 'SEGMENT-FILTER' rule 10 prefix '10.1.0.0/16'
   set vpp acl mac tag-name 'SEGMENT-FILTER' rule 10 description 'Management VLAN'
   
   # Allow user VLAN devices
   set vpp acl mac tag-name 'SEGMENT-FILTER' rule 20 action permit
   set vpp acl mac tag-name 'SEGMENT-FILTER' rule 20 mac-address '02:02:00:00:00:00'
   set vpp acl mac tag-name 'SEGMENT-FILTER' rule 20 mac-mask 'ff:ff:00:00:00:00'
   set vpp acl mac tag-name 'SEGMENT-FILTER' rule 20 prefix '10.2.0.0/16'
   set vpp acl mac tag-name 'SEGMENT-FILTER' rule 20 description 'User VLAN'

Applying MAC ACL Tags to Interfaces
-------------------------------------

MAC ACL tags can only be applied to the input direction of interfaces:

.. code-block:: none

   set vpp acl mac interface <interface> tag-name <tag-name>

.. note::
   **Syntax Difference**: Unlike IP ACLs, MAC ACL interface application does not use the ``acl-tag <number>`` structure since only single MAC ACLs can be applied.

.. warning::
   Unlike IP ACLs, MAC ACLs do **not** support output direction filtering. There is no ``output`` option available for MAC ACL interface application.

Example:

.. code-block:: none

   # Apply MAC filtering to interface input
   set vpp acl mac interface eth0 tag-name 'MAC-FILTER'
   set vpp acl mac interface eth1 tag-name 'DEVICE-WHITELIST'

Configuration Best Practices
============================

Rule Ordering
-------------

- **Number rules strategically**: Use gaps between rule numbers (10, 20, 30) to allow for future insertions
- **Place specific rules first**: More specific matches should have lower rule numbers
- **End with catch-all**: Always include a final rule that matches all traffic with explicit action
- **Document rules**: Use descriptions for complex rules to aid troubleshooting

Performance Considerations
--------------------------

- **Minimize rule count**: Fewer rules generally mean better performance
- **Use appropriate ACL type**: Use MAC ACLs for Layer 2/3 filtering, IP ACLs for Layer 3/4 filtering
- **Consider direction limitations**: Remember that MAC ACLs only work on input traffic; use IP ACLs for filtering in both directions
- **Combine related rules**: Group similar filtering requirements into single ACL tags
- **Apply strategically**: Apply ACLs at ingress points where possible to minimize processing

Troubleshooting
===============

Common Issues
-------------

* **ACL not taking effect:**

  - Verify ACL is applied to correct interface and direction
  - Check rule numbering and order
  - Ensure interface is properly configured in VPP

* **Performance degradation:**

  - Review ACL complexity and rule count
  - Consider consolidating rules
  - Check for unnecessary broad matches

* **Traffic blocked unexpectedly:**

  - Review rule order (first match wins)
  - Check for overly restrictive rules
  - Verify protocol and port specifications

Verification Commands
---------------------

Use these commands to verify ACL configuration and operation:

.. code-block:: none

   # Show VPP ACL configuration
   show configuration commands | grep "vpp acl"
   
   # Show VPP interface configuration
   show configuration commands | grep "vpp acl.*interface"
   
   # View commit history for ACL changes
   show configuration commit-revisions | grep -A5 -B5 "vpp acl"

Operational Commands
====================

VyOS provides several operational commands to monitor and troubleshoot VPP ACL configurations and their status.

Viewing All ACLs
----------------

Display all configured ACLs (both IP and MAC):

.. opcmd:: show vpp acl

This command shows a summary of all configured ACL tags with their rules, displaying both IP ACLs and MAC ACLs in a tabular format.

Example output:

.. code-block:: none

    ---------------------------------
    IP ACL "tag-name WEB-SERVER" acl_index 0

    Rule  Action    Src prefix    Src port    Dst prefix    Dst port      Proto  TCP flags set    TCP flags not set
    ------  --------  ------------  ----------  ------------  ----------  -------  ---------------  -------------------
        10  permit    0.0.0.0/0     0-65535     0.0.0.0/0     80                6
        20  permit    0.0.0.0/0     0-65535     0.0.0.0/0     443               6
        999  deny     0.0.0.0/0     0-65535     0.0.0.0/0     0-65535           0

    ---------------------------------
    MACIP ACL "tag-name VENDOR-FILTER" acl_index 0

    Rule  Action    IP prefix    MAC address        MAC mask
    ------  --------  -----------  -----------------  -----------------
        10  deny      0.0.0.0/0    00:e0:4c:00:00:00  ff:ff:ff:00:00:00
        100  permit   0.0.0.0/0    00:00:00:00:00:00  00:00:00:00:00:00

IP ACL Commands
---------------

View all IP ACLs:

.. opcmd:: show vpp acl ip

View IP ACL interface assignments:

.. opcmd:: show vpp acl ip interface

   show vpp acl ip interface

Example output:

.. code-block:: none

   Interface    Input ACLs    Output ACLs
   -----------  ------------  -------------
   eth1         WEB-SERVER

View specific IP ACL by tag name:

.. opcmd:: show vpp acl ip tag-name <tag-name>

Example:

.. code-block:: none

    vyos@vyos:~$ show vpp acl ip tag-name WEB-SERVER 

    ---------------------------------
    IP ACL "tag-name WEB-SERVER" acl_index 0

      Rule  Action    Src prefix    Src port    Dst prefix    Dst port      Proto  TCP flags set    TCP flags not set
    ------  --------  ------------  ----------  ------------  ----------  -------  ---------------  -------------------
        10  permit    0.0.0.0/0     0-65535     0.0.0.0/0     80                6
        20  permit    0.0.0.0/0     0-65535     0.0.0.0/0     443               6
       999  deny      0.0.0.0/0     0-65535     0.0.0.0/0     0-65535           0

MAC ACL Commands
------------------

View all MAC ACLs:

.. opcmd:: show vpp acl mac

View MAC ACL interface assignments:

.. opcmd:: show vpp acl mac interface

Example output:

.. code-block:: none

   Interface    ACL
   -----------  -----
   eth0         VENDOR-FILTER

View specific MAC ACL by tag name:

.. opcmd:: show vpp acl mac tag-name <tag-name>

Example:

.. code-block:: none

    vyos@vyos:~$ show vpp acl mac tag-name VENDOR-FILTER

    ---------------------------------
    MACIP ACL "tag-name VENDOR-FILTER" acl_index 0

      Rule  Action    IP prefix    MAC address        MAC mask
    ------  --------  -----------  -----------------  -----------------
        10  deny      0.0.0.0/0    00:e0:4c:00:00:00  ff:ff:ff:00:00:00
       100  permit    0.0.0.0/0    00:00:00:00:00:00  00:00:00:00:00:00

Understanding Command Output
----------------------------

**IP ACL Output Fields:**

- **Rule**: Rule number within the ACL
- **Action**: permit, deny, or permit-reflect
- **Src prefix**: Source IP prefix (0.0.0.0/0 = any source)
- **Src port**: Source port range (0-65535 = any port)
- **Dst prefix**: Destination IP prefix
- **Dst port**: Destination port or port range
- **Proto**: IP protocol number (6=TCP, 17=UDP, 1=ICMP, 0=any)
- **TCP flags set**: Required TCP flags (for TCP protocol)
- **TCP flags not set**: Prohibited TCP flags (for TCP protocol)

**MAC ACL Output Fields:**

- **Rule**: Rule number within the ACL
- **Action**: permit or deny
- **IP prefix**: Source IP prefix constraint
- **MAC address**: Source MAC address to match
- **MAC mask**: MAC address mask for partial matching

**Interface Assignment Output:**

- Shows which interfaces have ACLs applied
- **Input ACLs**: ACL tags applied to incoming traffic
- **Output ACLs**: ACL tags applied to outgoing traffic (IP ACLs only)
- **ACL**: MAC ACL tag applied to interface (input only)
