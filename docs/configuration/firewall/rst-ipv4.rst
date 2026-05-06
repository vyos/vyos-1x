:lastproofread: 2026-03-30

.. _firewall-ipv4-configuration:

###########################
IPv4 Firewall Configuration
###########################

********
Overview
********

This section provides information on IPv4 firewall configuration and
appropriate operation-mode commands. This section covers the following
configuration commands:

.. cfgcmd:: set firewall ipv4 ...

To learn about the general traffic flow in VyOS firewalls,
see :doc:`Firewall </configuration/firewall/index>`.

.. code-block:: none

   - set firewall
       * ipv4
            - forward
               + filter
            - input
               + filter
            - output
               + filter
               + raw
            - prerouting
               + raw
            - name
               + custom_name

First, the router receives all traffic and processes it in the **prerouting**
stage.

This stage includes:

   * **Firewall Prerouting**: commands found under ``set firewall ipv4
     prerouting raw ...``
   * :doc:`Conntrack Ignore</configuration/system/conntrack>`: ``set system
     conntrack ignore ipv4...``
   * :doc:`Policy Route</configuration/policy/route>`: commands found under
     ``set policy route ...``
   * :doc:`Destination NAT</configuration/nat/nat44>`: commands found under
     ``set nat destination ...``

For transit traffic, which is received by the router and forwarded, the base
chain is **forward**. The following is a simplified packet flow diagram for
transit traffic:

.. figure:: /_static/images/firewall-fwd-packet-flow.*

The base firewall chain for configuring filtering rules for transit traffic is
``set firewall ipv4 forward filter ...``, which occurs in stage 5, highlighted
in red.

For traffic to the router itself, the base chain is **input**. For traffic
the router originates, the base chain is **output**. A simplified packet flow
diagram is shown next, which shows the path for traffic destined to the router
itself and traffic the router generates (starting from circle number 6):

.. figure:: /_static/images/firewall-input-packet-flow.*

The base chain for traffic towards the router is
``set firewall ipv4 input filter ...``

The base chain for traffic the router generates is ``set firewall ipv4
output ...``, where two sub-chains are available: **filter** and **raw**:

* **Output Prerouting**: ``set firewall ipv4 output raw ...``. As described
  in **Prerouting**, the system processes rules in this section before the
  connection tracking subsystem.
* **Output Filter**: ``set firewall ipv4 output filter ...``. The system
  processes rules in this section after the connection tracking subsystem.

.. note:: **Important note about default-actions:**
   If you do not define a default action for a base chain, the system sets
   the default action to **accept** for that chain. For custom chains, if you
   do not define a default action, the system sets the default-action to
   **drop**.

You can create custom firewall chains using the following commands:
``set firewall ipv4 name <name> ...``. To use a custom chain, you must define
a rule with the **action jump** and the appropriate **target** in a base
chain.

*********************
Firewall - IPv4 Rules
*********************

Each firewall rule has a
number, an action to apply if the rule matches, and the ability to specify
multiple matching criteria. Packets traverse rules numbered 1-999999, so order
is crucial. The system executes the rule action at the first match.

Actions
=======

If you define a rule, you must define an action for it. The action tells the
firewall what to do if all the criteria you define for that rule are met.

The action can be:

   * ``accept``: Accept the packet.

   * ``continue``: Continue parsing the next rule.

   * ``drop``: Drop the packet.

   * ``reject``: Reject the packet.

   * ``jump``: Jump to another custom chain.

   * ``return``: Return from the current chain and continue at the next rule
     of the last chain.

   * ``queue``: Enqueue packet to userspace.

   * ``synproxy``: Synproxy the packet.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999> action
   [accept | continue | drop | jump | queue | reject | return | synproxy]
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999> action
   [accept | continue | drop | jump | queue | reject | return | synproxy]
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999> action
   [accept | continue | drop | jump | queue | reject | return]
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999> action
   [accept | continue | drop | jump | queue | reject | return]

   This required setting defines the action of the current rule. If you set
   the action to jump, you must also specify a jump-target.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   jump-target <text>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   jump-target <text>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   jump-target <text>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   jump-target <text>

   Use this command only when the action is set to ``jump``. Specify the
   jump target.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   queue <0-65535>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   queue <0-65535>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   queue <0-65535>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   queue <0-65535>

   Use this command only when the action is set to ``queue``. Specify the
   queue target to use. Queue range is also supported.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   queue-options bypass
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   queue-options bypass
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   queue-options bypass
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   queue-options bypass

   Use this command only when the action is set to ``queue``. Allow the packet
   to pass through the firewall when no userspace software is connected to the
   queue.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   queue-options fanout
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   queue-options fanout
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   queue-options fanout
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   queue-options fanout

   Use this command only when the action is set to ``queue``. Distribute
   packets between several queues.

Also, **default-action** is an action that applies when a packet does not
match any rule in its chain. For base chains, possible options for
**default-action** are **accept** or **drop**. 

.. cfgcmd:: set firewall ipv4 forward filter default-action
   [accept | drop]
.. cfgcmd:: set firewall ipv4 input filter default-action
   [accept | drop]
.. cfgcmd:: set firewall ipv4 output filter default-action
   [accept | drop]
.. cfgcmd:: set firewall ipv4 name <name> default-action
   [accept | drop | jump | queue | reject | return]

   This command sets the default action of the rule-set if a packet does not
   match the criteria of any rule. If you set the default-action to ``jump``,
   you must also specify ``default-jump-target``. Note that for base chains,
   you can set the default action only to ``accept`` or ``drop``, while on
   custom chains, more actions are available.

.. cfgcmd:: set firewall ipv4 name <name> default-jump-target <text>

   Use this command only when you set ``default-action`` to ``jump``. Specify
   the jump target for the default rule.

.. note:: **Important note about default-actions:**
   If you do not define a default action for a base chain, the system sets
   the default action to **accept** for that chain. For custom chains, if you
   do not define a default action, the system sets the default-action to
   **drop**.

Firewall Logs
=============

You can enable logging for every single firewall rule. If you enable logging,
you can define other log options. 

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999> log
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999> log
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999> log
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999> log

   Enable logging for the matched packet. If this command is not present, then
   logging is not enabled.

.. cfgcmd:: set firewall ipv4 forward filter default-log
.. cfgcmd:: set firewall ipv4 input filter default-log
.. cfgcmd:: set firewall ipv4 output filter default-log
.. cfgcmd:: set firewall ipv4 name <name> default-log

   Use this command to enable logging of the default action on the specified
   chain.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   log-options level [emerg | alert | crit | err | warn | notice
   | info | debug]
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   log-options level [emerg | alert | crit | err | warn | notice
   | info | debug]
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   log-options level [emerg | alert | crit | err | warn | notice
   | info | debug]
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   log-options level [emerg | alert | crit | err | warn | notice
   | info | debug]

   Define the log level. Only applicable if you enable rule logging.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   log-options group <0-65535>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   log-options group <0-65535>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   log-options group <0-65535>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   log-options group <0-65535>

   Define the log group to send messages to. Only applicable if you enable rule
   logging.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   log-options snapshot-length <0-9000>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   log-options snapshot-length <0-9000>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   log-options snapshot-length <0-9000>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   log-options snapshot-length <0-9000>

   Define the length of packet payload to include in a netlink message. Only
   applicable if you enable rule logging and define the log group.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   log-options queue-threshold <0-65535>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   log-options queue-threshold <0-65535>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   log-options queue-threshold <0-65535>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   log-options queue-threshold <0-65535>

   Define the number of packets to queue inside the kernel before sending them
   to userspace. Only applicable if you enable rule logging and define the log
   group.

Firewall Description
====================

You can add a description for reference for every single rule and for every
defined custom chain.

.. cfgcmd:: set firewall ipv4 name <name> description <text>

   Provide a rule-set description for a custom firewall chain.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   description <text>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   description <text>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   description <text>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999> description <text>

   Provide a description for each rule.

Rule Status
===========

When you define a rule, it is enabled by default. In some cases, it is useful
to disable the rule rather than removing it.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999> disable
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999> disable
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999> disable
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999> disable

   Command for disabling a rule but keeping it in the configuration.

Matching criteria
=================

There are a lot of matching criteria against which the packet can be tested.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   connection-status nat [destination | source]
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   connection-status nat [destination | source]
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   connection-status nat [destination | source]
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   connection-status nat [destination | source]

   Match based on nat connection status.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   connection-mark <1-2147483647>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   connection-mark <1-2147483647>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   connection-mark <1-2147483647>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   connection-mark <1-2147483647>

   Match based on connection mark.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   conntrack-helper <module>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   conntrack-helper <module>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   conntrack-helper <module>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   conntrack-helper <module>

   Match based on connection tracking protocol helper module to secure use of 
   that helper module. See below for possible completions `<module>`. 

   .. code-block:: none

      Possible completions:
      ftp                  Related traffic from FTP helper
      h323                 Related traffic from H.323 helper
      pptp                 Related traffic from PPTP helper
      nfs                  Related traffic from NFS helper
      sip                  Related traffic from SIP helper
      tftp                 Related traffic from TFTP helper
      sqlnet               Related traffic from SQLNet helper

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   source address [address | addressrange | CIDR]
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   source address [address | addressrange | CIDR]
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   source address [address | addressrange | CIDR]
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   source address [address | addressrange | CIDR]

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   destination address [address | addressrange | CIDR]
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   destination address [address | addressrange | CIDR]
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   destination address [address | addressrange | CIDR]
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   destination address [address | addressrange | CIDR]

   Match criteria based on source and/or destination address. This is similar
   to the network groups part, but here you are able to negate the matching
   addresses.

   .. code-block:: none

      set firewall ipv4 name FOO rule 50 source address 192.0.2.10-192.0.2.11
      # with a '!' the rule match everything except the specified subnet
      set firewall ipv4 input filter FOO rule 51 source address !203.0.113.0/24

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   source address-mask [address]
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   source address-mask [address]
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   source address-mask [address]
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   source address-mask [address]

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   destination address-mask [address]
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   destination address-mask [address]
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   destination address-mask [address]
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   destination address-mask [address]

   An arbitrary netmask can be applied to mask addresses to only match against
   a specific portion.
   
   This functions for both individual addresses and address groups.

   .. code-block:: none

      # Match any IPv4 address with `11` as the 2nd octet and `13` as the forth octet
      set firewall ipv4 name FOO rule 100 destination address 0.11.0.13
      set firewall ipv4 name FOO rule 100 destination address-mask 0.255.0.255

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   source fqdn <fqdn>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   source fqdn <fqdn>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   source fqdn <fqdn>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   source fqdn <fqdn>
.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   destination fqdn <fqdn>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   destination fqdn <fqdn>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   destination fqdn <fqdn>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   destination fqdn <fqdn>

   Specify a Fully Qualified Domain Name as source/destination to match. Ensure
   that the router is able to resolve this dns query.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   source geoip country-code <country>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   source geoip country-code <country>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   source geoip country-code <country>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   source geoip country-code <country>

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   destination geoip country-code <country>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   destination geoip country-code <country>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   destination geoip country-code <country>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   destination geoip country-code <country>

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   source geoip inverse-match
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   source geoip inverse-match
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   source geoip inverse-match
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   source geoip inverse-match

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   destination geoip inverse-match
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   destination geoip inverse-match
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   destination geoip inverse-match
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   destination geoip inverse-match

   Match IP addresses based on its geolocation. More info: `geoip matching
   <https://wiki.nftables.org/wiki-nftables/index.php/GeoIP_matching>`_.
   Use inverse-match to match anything except the given country-codes.

Data is provided by DB-IP.com under CC-BY-4.0 license. Attribution required,
permits redistribution so we can include a database in images(~3MB
compressed). Includes cron script (manually callable by op-mode update
geoip) to keep database and rules updated.


.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   source mac-address <mac-address>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   source mac-address <mac-address>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   source mac-address <mac-address>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   source mac-address <mac-address>

   You can only specify a source mac-address to match.

   .. code-block:: none

      set firewall ipv4 input filter rule 100 source mac-address 00:53:00:11:22:33
      set firewall ipv4 input filter rule 101 source mac-address !00:53:00:aa:12:34

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   source port [1-65535 | portname | start-end]
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   source port [1-65535 | portname | start-end]
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   source port [1-65535 | portname | start-end]
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   source port [1-65535 | portname | start-end]

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   destination port [1-65535 | portname | start-end]
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   destination port [1-65535 | portname | start-end]
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   destination port [1-65535 | portname | start-end]
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   destination port [1-65535 | portname | start-end]

   A port can be set by number or name as defined in ``/etc/services``.

   .. code-block:: none

      set firewall ipv4 forward filter rule 10 source port '22'
      set firewall ipv4 forward filter rule 11 source port '!http'
      set firewall ipv4 forward filter rule 12 source port 'https'

   Multiple source ports can be specified as a comma-separated list.
   The whole list can also be "negated" using ``!``. For example:

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   source group address-group <name | !name>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   source group address-group <name | !name>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   source group address-group <name | !name>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   source group address-group <name | !name>

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   destination group address-group <name | !name>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   destination group address-group <name | !name>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   destination group address-group <name | !name>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   destination group address-group <name | !name>

   Use a specific address-group. Prepending the character ``!`` to invert the
   criteria to match is also supported.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   source group dynamic-address-group <name | !name>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   source group dynamic-address-group <name | !name>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   source group dynamic-address-group <name | !name>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   source group dynamic-address-group <name | !name>

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   destination group dynamic-address-group <name | !name>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   destination group dynamic-address-group <name | !name>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   destination group dynamic-address-group <name | !name>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   destination group dynamic-address-group <name | !name>

   Use a specific dynamic-address-group. Prepending the character ``!`` to
   invert the criteria to match is also supported.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   source group network-group <name | !name>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   source group network-group <name | !name>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   source group network-group <name | !name>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   source group network-group <name | !name>

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   destination group network-group <name | !name>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   destination group network-group <name | !name>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   destination group network-group <name | !name>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   destination group network-group <name | !name>

   Use a specific network-group. Prepending the character ``!`` to invert the
   criteria to match is also supported.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   source group port-group <name | !name>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   source group port-group <name | !name>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   source group port-group <name | !name>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   source group port-group <name | !name>

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   destination group port-group <name | !name>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   destination group port-group <name | !name>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   destination group port-group <name | !name>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   destination group port-group <name | !name>

   Use a specific port-group. Prepending the character ``!`` to invert the
   criteria to match is also supported.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   source group domain-group <name | !name>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   source group domain-group <name | !name>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   source group domain-group <name | !name>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   source group domain-group <name | !name>

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   destination group domain-group <name | !name>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   destination group domain-group <name | !name>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   destination group domain-group <name | !name>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   destination group domain-group <name | !name>

   Use a specific domain-group. Prepending the character ``!`` to invert the
   criteria to match is also supported.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   source group mac-group <name | !name>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   source group mac-group <name | !name>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   source group mac-group <name | !name>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   source group mac-group <name | !name>

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   destination group mac-group <name | !name>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   destination group mac-group <name | !name>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   destination group mac-group <name | !name>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   destination group mac-group <name | !name>

   Use a specific mac-group. Prepending the character ``!`` to invert the
   criteria to match is also supported.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   dscp [0-63 | start-end]
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   dscp [0-63 | start-end]
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   dscp [0-63 | start-end]
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   dscp [0-63 | start-end]

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   dscp-exclude [0-63 | start-end]
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   dscp-exclude [0-63 | start-end]
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   dscp-exclude [0-63 | start-end]
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   dscp-exclude [0-63 | start-end]

   Match based on dscp value.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   fragment [match-frag | match-non-frag]
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   fragment [match-frag | match-non-frag]
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   fragment [match-frag | match-non-frag]
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   fragment [match-frag | match-non-frag]

   Match based on fragmentation.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   icmp [code | type] <0-255>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   icmp [code | type] <0-255>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   icmp [code | type] <0-255>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   icmp [code | type] <0-255>

   Match based on icmp code and type.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   icmp type-name <text>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   icmp type-name <text>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   icmp type-name <text>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   icmp type-name <text>

   Match based on icmp type-name. Use tab for information
   about what **type-name** criteria are supported.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   inbound-interface name <iface>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   inbound-interface name <iface>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   inbound-interface name <iface>

   Match based on inbound interface. Wildcard ``*`` is supported. For example:
   ``eth2*``. Prepend the character ``!`` to invert the criteria. For example:
   ``!eth2``

.. note:: If an interface is attached to a non-default vrf, when using
   **inbound-interface**, the vrf name must be used. For example ``set firewall
   ipv4 forward filter rule 10 inbound-interface name MGMT``

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   inbound-interface group <iface_group>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   inbound-interface group <iface_group>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   inbound-interface group <iface_group>

   Match based on the inbound interface group. Prepend the character ``!`` to
   invert the criteria. For example, ``!IFACE_GROUP``

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   outbound-interface name <iface>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   outbound-interface name <iface>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   outbound-interface name <iface>

   Match based on outbound interface. Wildcard ``*`` is supported. For example:
   ``eth2*``. Prepend the character ``!`` to invert the criteria. For example:
   ``!eth2``

.. note:: If an interface is attached to a non-default vrf, when using
   **outbound-interface**, the real interface name must be used. For example
   ``set firewall ipv4 forward filter rule 10 outbound-interface name eth0``

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   outbound-interface group <iface_group>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   outbound-interface group <iface_group>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   outbound-interface group <iface_group>

   Match based on outbound interface group. Prepend the character ``!`` to
   invert the criteria. For example: ``!IFACE_GROUP``

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   ipsec [match-ipsec-in | match-ipsec-out | match-none-in | match-none-out]
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   ipsec [match-ipsec-in | match-none-in]
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   ipsec [match-ipsec-out | match-none-out]
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   ipsec [match-ipsec-in | match-ipsec-out | match-none-in | match-none-out]

   Match based on ipsec.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   limit burst <0-4294967295>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   limit burst <0-4294967295>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   limit burst <0-4294967295>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   limit burst <0-4294967295>

   Match based on the maximum number of packets to allow in excess of rate.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   limit rate <text>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   limit rate <text>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   limit rate <text>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   limit rate <text>

   Specify the maximum average rate as **integer/unit**. For example:
   **5/minutes**

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   packet-length <text>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   packet-length <text>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   packet-length <text>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   packet-length <text>

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   packet-length-exclude <text>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   packet-length-exclude <text>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   packet-length-exclude <text>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   packet-length-exclude <text>

   Match based on packet length. Specify multiple values from 1 to 65535 and
   ranges.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   packet-type [broadcast | host | multicast | other]
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   packet-type [broadcast | host | multicast | other]
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   packet-type [broadcast | host | multicast | other]
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   packet-type [broadcast | host | multicast | other]

   Match based on the packet type.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   protocol [<text> | <0-255> | all | tcp_udp]
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   protocol [<text> | <0-255> | all | tcp_udp]
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   protocol [<text> | <0-255> | all | tcp_udp]
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   protocol [<text> | <0-255> | all | tcp_udp]

   Match based on protocol number or name as defined in ``/etc/protocols``.
   Special names are ``all`` for all protocols and ``tcp_udp`` for TCP and UDP
   based packets. The ``!`` character negates the selected protocol.

   .. code-block:: none

      set firewall ipv4 forward filter rule 10 protocol tcp_udp
      set firewall ipv4 forward filter rule 11 protocol !tcp_udp

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   recent count <1-255>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   recent count <1-255>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   recent count <1-255>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   recent count <1-255>

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   recent time [second | minute | hour]
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   recent time [second | minute | hour]
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   recent time [second | minute | hour]
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   recent time [second | minute | hour]

   Match based on recently seen sources.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   tcp flags [not] <text>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   tcp flags [not] <text>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   tcp flags [not] <text>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   tcp flags [not] <text>

   Specify TCP flags. Allowed values are ``ack``, ``cwr``, ``ecn``, ``fin``,
   ``psh``, ``rst``, ``syn``, and ``urg``. Specify multiple values, and use
   ``not`` for inverted selection, as shown in the example.

   .. code-block:: none

      set firewall ipv4 input filter rule 10 tcp flags 'ack'
      set firewall ipv4 input filter rule 12 tcp flags 'syn'
      set firewall ipv4 input filter rule 13 tcp flags not 'fin'

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   state [established | invalid | new | related]
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   state [established | invalid | new | related]
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   state [established | invalid | new | related]
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   state [established | invalid | new | related]

   Match against the state of a packet.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   time startdate <text>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   time startdate <text>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   time startdate <text>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   time startdate <text>
.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   time starttime <text>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   time starttime <text>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   time starttime <text>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   time starttime <text>
.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   time stopdate <text>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   time stopdate <text>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   time stopdate <text>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   time stopdate <text>
.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   time stoptime <text>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   time stoptime <text>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   time stoptime <text>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   time stoptime <text>
.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   time weekdays <text>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   time weekdays <text>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   time weekdays <text>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   time weekdays <text>

   Time to match the defined rule.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   ttl <eq | gt | lt> <0-255>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   ttl <eq | gt | lt> <0-255>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   ttl <eq | gt | lt> <0-255>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   ttl <eq | gt | lt> <0-255>

   Match the time to live parameter, where 'eq' means 'equal', 'gt' means
   'greater than', and 'lt' means 'less than'.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   recent count <1-255>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   recent count <1-255>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   recent count <1-255>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   recent count <1-255>

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   recent time <second | minute | hour>
.. cfgcmd:: set firewall ipv4 input filter rule <1-999999>
   recent time <second | minute | hour>
.. cfgcmd:: set firewall ipv4 output filter rule <1-999999>
   recent time <second | minute | hour>
.. cfgcmd:: set firewall ipv4 name <name> rule <1-999999>
   recent time <second | minute | hour>

   Match when 'count' amount of connections appear within 'time'. Use these
   matching criteria to block brute-force attempts.

Packet Modifications
====================

Starting from **VyOS-1.5-rolling-202410060007**, the firewall can modify
packets before sending them out. This feature provides more flexibility in
packet handling.

.. cfgcmd:: set firewall ipv4 prerouting raw rule <1-999999>
   set dscp <0-63>
.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   set dscp <0-63>
.. cfgcmd:: set firewall ipv4 output [filter | raw] rule <1-999999>
   set dscp <0-63>

   Set a specific value of Differentiated Services Codepoint (DSCP).

.. cfgcmd:: set firewall ipv4 prerouting raw rule <1-999999>
   set mark <1-2147483647>
.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   set mark <1-2147483647>
.. cfgcmd:: set firewall ipv4 output [filter | raw] rule <1-999999>
   set mark <1-2147483647>

   Set a specific packet mark value.

.. cfgcmd:: set firewall ipv4 prerouting raw rule <1-999999>
   set tcp-mss <500-1460>
.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   set tcp-mss <500-1460>
.. cfgcmd:: set firewall ipv4 output [filter | raw] rule <1-999999>
   set tcp-mss <500-1460>

   Set the TCP-MSS (TCP maximum segment size) for the connection.

.. cfgcmd:: set firewall ipv4 prerouting raw rule <1-999999>
   set ttl <0-255>
.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   set ttl <0-255>
.. cfgcmd:: set firewall ipv4 output [filter | raw] rule <1-999999>
   set ttl <0-255>

   Set the TTL (Time to Live) value.

.. cfgcmd:: set firewall ipv4 forward filter rule <1-999999>
   set connection-mark <0-2147483647>
.. cfgcmd:: set firewall ipv4 output [filter | raw] rule <1-999999>
   set connection-mark <0-2147483647>

   Set connection mark value.

********
Synproxy
********
Synproxy connections

.. cfgcmd:: set firewall ipv4 [input | forward] filter rule <1-999999>
   action synproxy
.. cfgcmd:: set firewall ipv4 [input | forward] filter rule <1-999999>
   protocol tcp
.. cfgcmd:: set firewall ipv4 [input | forward] filter rule <1-999999>
   synproxy tcp mss <501-65535>

    Set the TCP-MSS (maximum segment size) for the connection

.. cfgcmd:: set firewall ipv4 [input | forward] filter rule <1-999999>
   synproxy tcp window-scale <1-14>

    Set the window scale factor for TCP window scaling

Example synproxy
================
Requirements to enable synproxy:

  * Traffic must be symmetric.
  * Synproxy relies on syncookies and TCP timestamps, ensure these are enabled.
  * Disable conntrack loose track option.

.. code-block:: none

  set system sysctl parameter net.ipv4.tcp_timestamps value '1'

  set system conntrack tcp loose disable
  set system conntrack ignore ipv4 rule 10 destination port '8080'
  set system conntrack ignore ipv4 rule 10 protocol 'tcp'
  set system conntrack ignore ipv4 rule 10 tcp flags syn

  set firewall global-options syn-cookies 'enable'
  set firewall ipv4 input filter rule 10 action 'synproxy'
  set firewall ipv4 input filter rule 10 destination port '8080'
  set firewall ipv4 input filter rule 10 inbound-interface name 'eth1'
  set firewall ipv4 input filter rule 10 protocol 'tcp'
  set firewall ipv4 input filter rule 10 synproxy tcp mss '1460'
  set firewall ipv4 input filter rule 10 synproxy tcp window-scale '7'
  set firewall ipv4 input filter rule 1000 action 'drop'
  set firewall ipv4 input filter rule 1000 state invalid

***********************
Operation-mode Firewall
***********************

Rule-set overview
=================

.. opcmd:: show firewall

   This will show you a basic firewall overview, for all rule-sets, not
   only for IPv4.

   .. code-block:: none

      vyos@vyos:~$ show firewall
      Rulesets Information

      ---------------------------------
      ipv4 Firewall "forward filter"

      Rule     Action    Protocol      Packets    Bytes  Conditions
      -------  --------  ----------  ---------  -------  -----------------------------
      20       accept    all                 0        0  ip saddr @N_TRUSTEDv4  accept
      21       jump      all                 0        0  jump NAME_AUX
      default  accept    all                 0        0

      ---------------------------------
      ipv4 Firewall "input filter"

      Rule     Action    Protocol      Packets    Bytes  Conditions
      -------  --------  ----------  ---------  -------  -------------------------
      10       accept    all               156    14377  iifname != @I_LAN  accept
      default  accept    all                 0        0

      ---------------------------------
      ipv4 Firewall "name AUX"

        Rule  Action    Protocol      Packets    Bytes  Conditions
      ------  --------  ----------  ---------  -------  --------------------------------------------
          10  accept    icmp                0        0  meta l4proto icmp  accept
          20  accept    udp                 0        0  meta l4proto udp ip saddr @A_SERVERS  accept
          30  drop      all                 0        0  ip saddr != @A_SERVERS iifname "eth2"

      ---------------------------------
      ipv4 Firewall "output filter"

      Rule     Action    Protocol      Packets    Bytes  Conditions
      -------  --------  ----------  ---------  -------  ----------------------------------------
      10       reject    all                 0        0  oifname @I_LAN
      20       accept    icmp                2      168  meta l4proto icmp oifname "eth0"  accept
      default  accept    all                72     9258

      ---------------------------------
      ipv6 Firewall "input filter"

      Rule     Action    Protocol      Packets    Bytes  Conditions
      -------  --------  ----------  ---------  -------  -------------------------------
      10       accept    all                 0        0  ip6 saddr @N6_TRUSTEDv6  accept
      default  accept    all                 2      112

      vyos@vyos:~$ 

.. opcmd:: show firewall summary

   This shows you a summary of rule-sets and groups.

   .. code-block:: none

      vyos@vyos:~$ show firewall summary 
      Ruleset Summary

      IPv6 Ruleset:

      Ruleset Hook    Ruleset Priority      Description
      --------------  --------------------  -------------------------
      forward         filter
      input           filter
      ipv6_name       IPV6-VyOS_MANAGEMENT
      ipv6_name       IPV6-WAN_IN           PUBLIC_INTERNET

      IPv4 Ruleset:

      Ruleset Hook    Ruleset Priority    Description
      --------------  ------------------  -------------------------
      forward         filter
      input           filter
      name            VyOS_MANAGEMENT
      name            WAN_IN              PUBLIC_INTERNET

      Firewall Groups

      Name                     Type                References               Members
      -----------------------  ------------------  -----------------------  ----------------
      PBX                      address_group       WAN_IN-100               198.51.100.77
      SERVERS                  address_group       WAN_IN-110               192.0.2.10
                                                   WAN_IN-111               192.0.2.11
                                                   WAN_IN-112               192.0.2.12
                                                   WAN_IN-120
                                                   WAN_IN-121
                                                   WAN_IN-122
      SUPPORT                  address_group       VyOS_MANAGEMENT-20       192.168.1.2
                                                   WAN_IN-20
      PHONE_VPN_SERVERS        address_group       WAN_IN-160               10.6.32.2
      PINGABLE_ADRESSES        address_group       WAN_IN-170               192.168.5.2
                                                   WAN_IN-171
      PBX                      ipv6_address_group  IPV6-WAN_IN-100          2001:db8::1
      SERVERS                  ipv6_address_group  IPV6-WAN_IN-110          2001:db8::2
                                                   IPV6-WAN_IN-111          2001:db8::3
                                                   IPV6-WAN_IN-112          2001:db8::4
                                                   IPV6-WAN_IN-120
                                                   IPV6-WAN_IN-121
                                                   IPV6-WAN_IN-122
      SUPPORT                  ipv6_address_group  IPV6-VyOS_MANAGEMENT-20  2001:db8::5
                                                   IPV6-WAN_IN-20


.. opcmd:: show firewall ipv4 [forward | input | output] filter

.. opcmd:: show firewall ipv4 name <name>

   This command will give an overview of a single rule-set.

   .. code-block:: none

      vyos@vyos:~$ show firewall ipv4 input filter 
      Ruleset Information

      ---------------------------------
      IPv4 Firewall "input filter"

      Rule     Action    Protocol      Packets    Bytes  Conditions
      -------  --------  ----------  ---------  -------  -----------------------------------------
      5        jump      all                 0        0  iifname "eth2"  jump NAME_VyOS_MANAGEMENT
      default  accept    all

.. opcmd:: show firewall ipv4 [forward | input | output]
   filter rule <1-999999>
.. opcmd:: show firewall ipv4 name <name> rule <1-999999>

   This command gives an overview of a rule in a single rule-set, plus
   information for default action.

.. code-block:: none

      vyos@vyos:~$show firewall ipv4 output filter rule 20
      Rule Information

      ---------------------------------
      ipv4 Firewall "output filter"

      Rule     Action    Protocol      Packets    Bytes  Conditions
      -------  --------  ----------  ---------  -------  ----------------------------------------
      20       accept    icmp                2      168  meta l4proto icmp oifname "eth0"  accept
      default  accept    all               286    47614

      vyos@vyos:~$


.. opcmd:: show firewall statistics

   This will show you statistics of all rule-sets since the last boot.

Show Firewall log
=================

.. opcmd:: show log firewall
.. opcmd:: show log firewall ipv4
.. opcmd:: show log firewall ipv4 [forward | input | output | name]
.. opcmd:: show log firewall ipv4 [forward | input | output] filter
.. opcmd:: show log firewall ipv4 name <name>
.. opcmd:: show log firewall ipv4 [forward | input | output] filter rule <rule>
.. opcmd:: show log firewall ipv4 name <name> rule <rule>

   Show the logs of all firewall; show all IPv4 firewall logs; show all logs
   for particular hook; show all logs for particular hook and priority;
   show all logs for particular custom chain; show logs for specific rule-set.

Example Partial Config
======================

.. code-block:: none

  firewall {
      group {
          network-group BAD-NETWORKS {
              network 198.51.100.0/24
              network 203.0.113.0/24
          }
          network-group GOOD-NETWORKS {
              network 192.0.2.0/24
          }
          port-group BAD-PORTS {
              port 65535
          }
      }
      ipv4 {
          forward {
              filter {
                  default-action accept
                  rule 5 {
                      action accept
                      source {
                          group {
                              network-group GOOD-NETWORKS
                          }
                      }
                  }
                  rule 10 {
                      action drop
                      description "Bad Networks"
                      protocol all
                      source {
                          group {
                              network-group BAD-NETWORKS
                          }
                      }
                  }
              }
          }
      }
  }

Update geoip database
=====================

.. opcmd:: update geoip

   Command to update GeoIP database and firewall sets.
