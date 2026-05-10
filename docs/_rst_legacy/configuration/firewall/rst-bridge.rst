:lastproofread: 2026-03-28

.. _firewall-configuration:

#############################
Bridge Firewall Configuration
#############################

********
Overview
********

Learn more about bridge firewall configuration
and related op-mode commands.

The following commands are covered in this section:

.. cfgcmd:: set firewall bridge <options>

From the main structure defined in
:doc:`Firewall Overview</configuration/firewall/index>`
in this section you can find detailed information only for the next part
of the general structure:

.. code-block:: none

   - set firewall
       * bridge
            - forward
               + filter
            - input
               + filter
            - output
               + filter
            - prerouting
               + filter
            - name
               + custom_name

Traffic that is received by the router on an interface that is a member of a
bridge is processed on the **Bridge Layer**. Before the bridge decision is
made, all packets are analyzed at **Prerouting**. First filters can be applied
here, and also rules for ignoring connection tracking system can be configured.
The relevant configuration that acts in **prerouting** is:

  * ``set firewall bridge prerouting filter ...``.

For traffic that needs to be switched internally by the bridge, the base
chain is **forward**, and its base command for filtering is ``set firewall
bridge forward filter ...``, which happens in stage 4, highlighted with red
color.

.. figure:: /_static/images/firewall-bridge-forward.*

For traffic destined to the router itself or that needs to be routed
(assuming a layer3 bridge is configured), the base chain is **input**, and the
base command is ``set firewall bridge input filter ...`` and the path is:

.. figure:: /_static/images/firewall-bridge-input.*

If it's not dropped, then the packet is sent to **IP Layer**, and will be
processed by the **IP Layer** firewall: IPv4 or IPv6 ruleset. Check once again
the :doc:`general packet flow diagram</configuration/firewall/index>` if
needed.

For traffic that originates from the bridge itself, the base chain is
**output**, and the base command is ``set firewall bridge output filter
...``, and the path is:

.. figure:: /_static/images/firewall-bridge-output.*

Custom bridge firewall chains can be created with the command ``set firewall
bridge name <name> ...``. To use such a custom chain, a rule with action jump
and the appropriate target must be defined in a base chain.

************
Bridge Rules
************

For firewall filtering, firewall rules need to be created. Each rule is
numbered, has an action to apply if the rule is matched, and the ability
to specify multiple matching criteria. Data packets go through the rules
from 1 - 999999, so order is crucial. At the first match the action of the
rule will be executed.

Actions
=======

If a rule is defined, an action must also be defined for it. This tells the
firewall what to do if all matching criteria in the rule are met.

In firewall bridge rules, the action can be:

   * ``accept``: accept the packet.

   * ``continue``: continue parsing next rule.

   * ``drop``: drop the packet.

   * ``jump``: jump to another custom chain.

   * ``return``: Return from the current chain and continue at the next rule
     of the last chain.

   * ``queue``: Enqueue packet to userspace.

   * ``notrack``: ignore connection tracking system. This action is only
     available in prerouting chain.

.. cfgcmd:: set firewall bridge forward filter rule <1-999999> action
   [accept | continue | drop | jump | queue | return]
.. cfgcmd:: set firewall bridge input filter rule <1-999999> action
   [accept | continue | drop | jump | queue | return]
.. cfgcmd:: set firewall bridge output filter rule <1-999999> action
   [accept | continue | drop | jump | queue | return]
.. cfgcmd:: set firewall bridge prerouting filter rule <1-999999> action
   [accept | continue | drop | jump | notrack | queue | return]
.. cfgcmd:: set firewall bridge name <name> rule <1-999999> action
   [accept | continue | drop | jump | queue | return]

   This required setting defines the action of the current rule. If action is
   set to jump, then jump-target is also needed.

.. cfgcmd:: set firewall bridge forward filter rule <1-999999>
   jump-target <text>
.. cfgcmd:: set firewall bridge input filter rule <1-999999>
   jump-target <text>
.. cfgcmd:: set firewall bridge output filter rule <1-999999>
   jump-target <text>
.. cfgcmd:: set firewall bridge prerouting filter rule <1-999999>
   jump-target <text>
.. cfgcmd:: set firewall bridge name <name> rule <1-999999>
   jump-target <text>

   If action is set to ``queue``, use next command to specify the queue
   target. Range is also supported:

.. cfgcmd:: set firewall bridge forward filter rule <1-999999>
   queue <0-65535>
.. cfgcmd:: set firewall bridge input filter rule <1-999999>
   queue <0-65535>
.. cfgcmd:: set firewall bridge output filter rule <1-999999>
   queue <0-65535>
.. cfgcmd:: set firewall bridge prerouting filter rule <1-999999>
   queue <0-65535>
.. cfgcmd:: set firewall bridge name <name> rule <1-999999>
   queue <0-65535>

   Also, if action is set to ``queue``, use next command to specify the queue
   options. Possible options are ``bypass`` and ``fanout``:

.. cfgcmd:: set firewall bridge forward filter rule <1-999999>
   queue-options bypass
.. cfgcmd:: set firewall bridge input filter rule <1-999999>
   queue-options bypass
.. cfgcmd:: set firewall bridge output filter rule <1-999999>
   queue-options bypass
.. cfgcmd:: set firewall bridge prerouting filter rule <1-999999>
   queue-options bypass
.. cfgcmd:: set firewall bridge name <name> rule <1-999999>
   queue-options bypass

.. cfgcmd:: set firewall bridge forward filter rule <1-999999>
   queue-options fanout
.. cfgcmd:: set firewall bridge input filter rule <1-999999>
   queue-options fanout
.. cfgcmd:: set firewall bridge output filter rule <1-999999>
   queue-options fanout
.. cfgcmd:: set firewall bridge prerouting filter rule <1-999999>
   queue-options fanout
.. cfgcmd:: set firewall bridge name <name> rule <1-999999>
   queue-options fanout

Also, **default-action** is an action that takes place whenever a packet does
not match any rule in its chain. For base chains, possible options for
**default-action** are **accept** or **drop**.

.. cfgcmd:: set firewall bridge forward filter default-action
   [accept | drop]
.. cfgcmd:: set firewall bridge input filter default-action
   [accept | drop]
.. cfgcmd:: set firewall bridge output filter default-action
   [accept | drop]
.. cfgcmd:: set firewall bridge prerouting filter default-action
   [accept | drop]
.. cfgcmd:: set firewall bridge name <name> default-action
   [accept | continue | drop | jump | reject | return]

   This sets the default action of the rule-set if a packet does not match
   any of the rules in that chain. If default-action is set to ``jump``, then
   ``default-jump-target`` is also needed. Note that for base chains, default
   action can only be set to ``accept`` or ``drop``, while on custom chains
   more actions are available.

.. cfgcmd:: set firewall bridge name <name> default-jump-target <text>

   To be used only when ``default-action`` is set to ``jump``. Use this
   command to specify jump target for default rule.

.. note:: **Important note about default-actions:**
   If the default action for any base chain is not defined, then the default
   action is set to **accept** for that chain. For custom chains, if the 
   default action is not defined, then the default-action is set to **drop**.

Firewall Logs
=============

You can enable logging for every firewall rule. If enabled, other log options
can be configured.

.. cfgcmd:: set firewall bridge forward filter rule <1-999999> log
.. cfgcmd:: set firewall bridge input filter rule <1-999999> log
.. cfgcmd:: set firewall bridge output filter rule <1-999999> log
.. cfgcmd:: set firewall bridge prerouting filter rule <1-999999> log
.. cfgcmd:: set firewall bridge name <name> rule <1-999999> log

   Enable logging for the matched packet. If this configuration command is not
   present, then the log is not enabled.

.. cfgcmd:: set firewall bridge forward filter default-log
.. cfgcmd:: set firewall bridge input filter default-log
.. cfgcmd:: set firewall bridge output filter default-log
.. cfgcmd:: set firewall bridge prerouting filter default-log
.. cfgcmd:: set firewall bridge name <name> default-log

   Use this command to enable the logging of the default action on
   the specified chain.

.. cfgcmd:: set firewall bridge forward filter rule <1-999999>
   log-options level [emerg | alert | crit | err | warn | notice
   | info | debug]
.. cfgcmd:: set firewall bridge input filter rule <1-999999>
   log-options level [emerg | alert | crit | err | warn | notice
   | info | debug]
.. cfgcmd:: set firewall bridge output filter rule <1-999999>
   log-options level [emerg | alert | crit | err | warn | notice
   | info | debug]
.. cfgcmd:: set firewall bridge prerouting filter rule <1-999999>
   log-options level [emerg | alert | crit | err | warn | notice
   | info | debug]
.. cfgcmd:: set firewall bridge name <name> rule <1-999999>
   log-options level [emerg | alert | crit | err | warn | notice
   | info | debug]

   Define log-level. Only applicable if rule log is enabled.

.. cfgcmd:: set firewall bridge forward filter rule <1-999999>
   log-options group <0-65535>
.. cfgcmd:: set firewall bridge input filter rule <1-999999>
   log-options group <0-65535>
.. cfgcmd:: set firewall bridge output filter rule <1-999999>
   log-options group <0-65535>
.. cfgcmd:: set firewall bridge prerouting filter rule <1-999999>
   log-options group <0-65535>
.. cfgcmd:: set firewall bridge name <name> rule <1-999999>
   log-options group <0-65535>

   Define the log group to send messages to. Only applicable if rule log is
   enabled.

.. cfgcmd:: set firewall bridge forward filter rule <1-999999>
   log-options snapshot-length <0-9000>
.. cfgcmd:: set firewall bridge input filter rule <1-999999>
   log-options snapshot-length <0-9000>
.. cfgcmd:: set firewall bridge output filter rule <1-999999>
   log-options snapshot-length <0-9000>
.. cfgcmd:: set firewall bridge prerouting filter rule <1-999999>
   log-options snapshot-length <0-9000>
.. cfgcmd:: set firewall bridge name <name> rule <1-999999>
   log-options snapshot-length <0-9000>

   Define length of packet payload to include in netlink message. Only
   applicable if rule log is enabled and the log group is defined.

.. cfgcmd:: set firewall bridge forward filter rule <1-999999>
   log-options queue-threshold <0-65535>
.. cfgcmd:: set firewall bridge input filter rule <1-999999>
   log-options queue-threshold <0-65535>
.. cfgcmd:: set firewall bridge output filter rule <1-999999>
   log-options queue-threshold <0-65535>
.. cfgcmd:: set firewall bridge prerouting filter rule <1-999999>
   log-options queue-threshold <0-65535>
.. cfgcmd:: set firewall bridge name <name> rule <1-999999>
   log-options queue-threshold <0-65535>

   Define the number of packets to queue inside the kernel before sending them
   to userspace. Only applicable if rule log is enabled and the log group is 
   defined.

Firewall Description
====================

You can define a description for reference for every custom chain.

.. cfgcmd:: set firewall bridge name <name> description <text>

   Provide a rule-set description to a custom firewall chain.

.. cfgcmd:: set firewall bridge forward filter rule <1-999999>
   description <text>
.. cfgcmd:: set firewall bridge input filter rule <1-999999>
   description <text>
.. cfgcmd:: set firewall bridge output filter rule <1-999999>
   description <text>
.. cfgcmd:: set firewall bridge prerouting filter rule <1-999999>
   description <text>
.. cfgcmd:: set firewall bridge name <name> rule <1-999999>
   description <text>

   Provide a description for each rule.

Rule Status
===========

By default, when you define a rule, it is enabled. In some cases, it is
useful to disable the rule instead of removing it.

.. cfgcmd:: set firewall bridge forward filter rule <1-999999> disable
.. cfgcmd:: set firewall bridge input filter rule <1-999999> disable
.. cfgcmd:: set firewall bridge output filter rule <1-999999> disable
.. cfgcmd:: set firewall bridge prerouting filter rule <1-999999> disable
.. cfgcmd:: set firewall bridge name <name> rule <1-999999> disable

   Command for disabling a rule but keep it in the configuration.

Matching criteria
=================

There are many matching criteria against which a packet can be tested. Refer
to :doc:`IPv4</configuration/firewall/ipv4>` and
:doc:`IPv6</configuration/firewall/ipv6>` matching criteria for more details.

Since bridges operate at layer 2, both matchers for IPv4 and IPv6 are
supported in bridge firewall configuration. Same applies to firewall groups.

Same specific matching criteria that can be used in bridge firewall are
described in this section:

.. cfgcmd:: set firewall bridge forward filter rule <1-999999> ethernet-type
   [802.1q | 802.1ad | arp | ipv4 | ipv6]
.. cfgcmd:: set firewall bridge input filter rule <1-999999> ethernet-type
   [802.1q | 802.1ad | arp | ipv4 | ipv6]
.. cfgcmd:: set firewall bridge output filter rule <1-999999> ethernet-type
   [802.1q | 802.1ad | arp | ipv4 | ipv6]
.. cfgcmd:: set firewall bridge prerouting filter rule <1-999999> ethernet-type
   [802.1q | 802.1ad | arp | ipv4 | ipv6]
.. cfgcmd:: set firewall bridge name <name> rule <1-999999> ethernet-type
   [802.1q | 802.1ad | arp | ipv4 | ipv6]

   Match based on the Ethernet type of the packet.

.. cfgcmd:: set firewall bridge forward filter rule <1-999999> vlan
   ethernet-type [802.1q | 802.1ad | arp | ipv4 | ipv6]
.. cfgcmd:: set firewall bridge input filter rule <1-999999> vlan
   ethernet-type [802.1q | 802.1ad | arp | ipv4 | ipv6]
.. cfgcmd:: set firewall bridge output filter rule <1-999999> vlan
   ethernet-type [802.1q | 802.1ad | arp | ipv4 | ipv6]
.. cfgcmd:: set firewall bridge prerouting filter rule <1-999999> vlan
   ethernet-type [802.1q | 802.1ad | arp | ipv4 | ipv6]
.. cfgcmd:: set firewall bridge name <name> rule <1-999999> vlan
   ethernet-type [802.1q | 802.1ad | arp | ipv4 | ipv6]

   Match based on the Ethernet type of the packet when it is VLAN tagged.

.. cfgcmd:: set firewall bridge forward filter rule <1-999999> vlan id
   <0-4096>
.. cfgcmd:: set firewall bridge input filter rule <1-999999> vlan id
   <0-4096>
.. cfgcmd:: set firewall bridge output filter rule <1-999999> vlan id
   <0-4096>
.. cfgcmd:: set firewall bridge prerouting filter rule <1-999999> vlan id
   <0-4096>
.. cfgcmd:: set firewall bridge name <name> rule <1-999999> vlan id
   <0-4096>

   Match based on VLAN identifier. Range is also supported.

.. cfgcmd:: set firewall bridge forward filter rule <1-999999> vlan priority
   <0-7>
.. cfgcmd:: set firewall bridge input filter rule <1-999999> vlan priority
   <0-7>
.. cfgcmd:: set firewall bridge output filter rule <1-999999> vlan priority
   <0-7>
.. cfgcmd:: set firewall bridge prerouting filter rule <1-999999> vlan priority
   <0-7>
.. cfgcmd:: set firewall bridge name <name> rule <1-999999> vlan priority
   <0-7>

   Match based on VLAN priority (Priority Code Point - PCP). Range is also
   supported.

Packet Modifications
====================

Starting from **VyOS-1.5-rolling-202410060007**, the firewall can modify
packets before they are sent out. This feaure provides more flexibility in
packet handling.

.. cfgcmd:: set firewall bridge [prerouting | forward | output] filter
   rule <1-999999> set dscp <0-63>

   Set a specific value of Differentiated Services Codepoint (DSCP).

.. cfgcmd:: set firewall bridge [prerouting | forward | output] filter
   rule <1-999999> set mark <1-2147483647>

   Set a specific packet mark value.

.. cfgcmd:: set firewall bridge [prerouting | forward | output] filter
   rule <1-999999> set tcp-mss <500-1460>

   Set the TCP-MSS (TCP maximum segment size) for the connection.

.. cfgcmd:: set firewall bridge [prerouting | forward | output] filter
   rule <1-999999> set ttl <0-255>

   Set the TTL (Time to Live) value.

.. cfgcmd:: set firewall bridge [prerouting | forward | output] filter
   rule <1-999999> set hop-limit <0-255>

   Set hop limit value.

.. cfgcmd:: set firewall bridge [forward | output] filter
   rule <1-999999> set connection-mark <0-2147483647>

   Set connection mark value.


Use IP firewall
===============

By default, for switched traffic, only the rules defined under ``set firewall
bridge`` are applied. There are two global-options that can be configured in
order to force deeper analysis of the packet on the IP layer. These options
are:

.. cfgcmd:: set firewall global-options apply-to-bridged-traffic ipv4

   This command enables the IPv4 firewall for bridged traffic. If this option
   is used, packets are also parsed by rules defined in ``set firewall ipv4
   ...`` 

.. cfgcmd:: set firewall global-options apply-to-bridged-traffic ipv6

   This command enables the IPv6 firewall for bridged traffic. If this option
   is used, packets are also parsed by rules defined in ``set firewall ipv6
   ...`` 

***********************
Operation-mode Firewall
***********************

Rule-set overview
=================

In this section you can find all useful firewall op-mode commands.

General commands for firewall configuration, counter and statistics:

.. opcmd:: show firewall
.. opcmd:: show firewall summary
.. opcmd:: show firewall statistics

And, to print only bridge firewall information:

.. opcmd:: show firewall bridge
.. opcmd:: show firewall bridge forward filter
.. opcmd:: show firewall bridge forward filter rule <rule>
.. opcmd:: show firewall bridge name <name>
.. opcmd:: show firewall bridge name <name> rule <rule>

Show Firewall log
=================

.. opcmd:: show log firewall
.. opcmd:: show log firewall bridge
.. opcmd:: show log firewall bridge forward
.. opcmd:: show log firewall bridge forward filter
.. opcmd:: show log firewall bridge name <name>
.. opcmd:: show log firewall bridge forward filter rule <rule>
.. opcmd:: show log firewall bridge name <name> rule <rule>

   Show the logs of all firewall; show all bridge firewall logs; show all logs
   for forward hook; show all logs for forward hook and priority filter; show
   all logs for particular custom chain; show logs for specific Rule-Set.

Example
=======

Configuration example:

.. code-block:: none

   set firewall bridge forward filter default-action 'drop'
   set firewall bridge forward filter default-log
   set firewall bridge forward filter rule 10 action 'continue'
   set firewall bridge forward filter rule 10 inbound-interface name 'eth2'
   set firewall bridge forward filter rule 10 vlan id '22'
   set firewall bridge forward filter rule 20 action 'drop'
   set firewall bridge forward filter rule 20 inbound-interface group 'TRUNK-RIGHT'
   set firewall bridge forward filter rule 20 vlan id '60'
   set firewall bridge forward filter rule 30 action 'jump'
   set firewall bridge forward filter rule 30 jump-target 'TEST'
   set firewall bridge forward filter rule 30 outbound-interface name '!eth1'
   set firewall bridge forward filter rule 35 action 'accept'
   set firewall bridge forward filter rule 35 vlan id '11'
   set firewall bridge forward filter rule 40 action 'continue'
   set firewall bridge forward filter rule 40 destination mac-address '66:55:44:33:22:11'
   set firewall bridge forward filter rule 40 source mac-address '11:22:33:44:55:66'
   set firewall bridge name TEST default-action 'accept'
   set firewall bridge name TEST default-log
   set firewall bridge name TEST rule 10 action 'continue'
   set firewall bridge name TEST rule 10 log
   set firewall bridge name TEST rule 10 vlan priority '0'

And op-mode commands:

.. code-block:: none

      vyos@BRI:~$ show firewall bridge
      Rulesets bridge Information

      ---------------------------------
      bridge Firewall "forward filter"

      Rule     Action    Protocol      Packets    Bytes  Conditions
      -------  --------  ----------  ---------  -------  ---------------------------------------------------------------------
      10       continue  all                 0        0  iifname "eth2" vlan id 22  continue
      20       drop      all                 0        0  iifname @I_TRUNK-RIGHT vlan id 60
      30       jump      all              2130   170688  oifname != "eth1"  jump NAME_TEST
      35       accept    all              2080   168616  vlan id 11  accept
      40       continue  all                 0        0  ether daddr 66:55:44:33:22:11 ether saddr 11:22:33:44:55:66  continue
      default  drop      all                 0        0

      ---------------------------------
      bridge Firewall "name TEST"

      Rule     Action    Protocol      Packets    Bytes  Conditions
      -------  --------  ----------  ---------  -------  --------------------------------------------------
      10       continue  all              2130   170688  vlan pcp 0  prefix "[bri-NAM-TEST-10-C]"  continue
      default  accept    all              2130   170688

      vyos@BRI:~$
      vyos@BRI:~$ show firewall bridge name TEST
      Ruleset Information

      ---------------------------------
      bridge Firewall "name TEST"

      Rule     Action    Protocol      Packets    Bytes  Conditions
      -------  --------  ----------  ---------  -------  --------------------------------------------------
      10       continue  all              2130   170688  vlan pcp 0  prefix "[bri-NAM-TEST-10-C]"  continue
      default  accept    all              2130   170688

      vyos@BRI:~$

Inspect logs:

.. stop_vyoslinter

.. code-block:: none

      vyos@BRI:~$ show log firewall bridge
      Dec 05 14:37:47 kernel: [bri-NAM-TEST-10-C]IN=eth1 OUT=eth2 ARP HTYPE=1 PTYPE=0x0800 OPCODE=1 MACSRC=50:00:00:04:00:00 IPSRC=10.11.11.101 MACDST=00:00:00:00:00:00 IPDST=10.11.11.102
      Dec 05 14:37:48 kernel: [bri-NAM-TEST-10-C]IN=eth1 OUT=eth2 ARP HTYPE=1 PTYPE=0x0800 OPCODE=1 MACSRC=50:00:00:04:00:00 IPSRC=10.11.11.101 MACDST=00:00:00:00:00:00 IPDST=10.11.11.102
      Dec 05 14:37:49 kernel: [bri-NAM-TEST-10-C]IN=eth1 OUT=eth2 ARP HTYPE=1 PTYPE=0x0800 OPCODE=1 MACSRC=50:00:00:04:00:00 IPSRC=10.11.11.101 MACDST=00:00:00:00:00:00 IPDST=10.11.11.102
      ...
      vyos@BRI:~$ show log firewall bridge forward filter
      Dec 05 14:42:22 kernel: [bri-FWD-filter-default-D]IN=eth2 OUT=eth1 MAC=33:33:00:00:00:16:50:00:00:06:00:00:86:dd SRC=0000:0000:0000:0000:0000:0000:0000:0000 DST=ff02:0000:0000:0000:0000:0000:0000:0016 LEN=96 TC=0 HOPLIMIT=1 FLOWLBL=0 PROTO=ICMPv6 TYPE=143 CODE=0
      Dec 05 14:42:22 kernel: [bri-FWD-filter-default-D]IN=eth2 OUT=eth1 MAC=33:33:00:00:00:16:50:00:00:06:00:00:86:dd SRC=0000:0000:0000:0000:0000:0000:0000:0000 DST=ff02:0000:0000:0000:0000:0000:0000:0016 LEN=96 TC=0 HOPLIMIT=1 FLOWLBL=0 PROTO=ICMPv6 TYPE=143 CODE=0

.. start_vyoslinter
