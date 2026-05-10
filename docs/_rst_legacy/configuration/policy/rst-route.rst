#######################
Route and Route6 Policy
#######################

IPv4 route and IPv6 route policies are defined in this section. These route
policies can then be associated to interfaces.

*********
Rule-Sets
*********

A rule-set is a named collection of rules that can be applied to an interface.
Each rule is numbered, has an action to apply if the rule is matched, and the
ability to specify the criteria to match. Data packets go through the rules
from 1 - 999999, at the first match the action of the rule will be executed.

.. cfgcmd:: set policy route <name> description <text>
.. cfgcmd:: set policy route6 <name> description <text>

   Provide a rule-set description.

.. cfgcmd:: set policy route <name> default-log
.. cfgcmd:: set policy route6 <name> default-log

   Option to log packets hitting default-action.

.. cfgcmd:: set policy route <name> interface <interface>
.. cfgcmd:: set policy route6 <name> interface <interface>

   Apply routing policy to interface

.. cfgcmd:: set policy route <name> rule <n> description <text>
.. cfgcmd:: set policy route6 <name> rule <n> description <text>

   Provide a description for each rule.

.. cfgcmd:: set policy route <name> rule <n> log <enable|disable>
.. cfgcmd:: set policy route6 <name> rule <n> log <enable|disable>

   Option to enable or disable log matching rule.

Matching criteria
=================

There are a lot of matching criteria options available, both for
``policy route`` and ``policy route6``. These options are listed
in this section.

.. cfgcmd:: set policy route <name> rule <n> connection-mark <1-2147483647>
.. cfgcmd:: set policy route6 <name> rule <n> connection-mark <1-2147483647>

  Set match criteria based on connection mark.

.. cfgcmd:: set policy route <name> rule <n> mark <match_criteria>
.. cfgcmd:: set policy route6 <name> rule <n> mark <match_criteria>

  Match based on the firewall mark (fwmark), where <match_criteria> can be:

   * <0-2147483647> a single fwmark
   * !<0-2147483647> everything except a single fwmark
   * <start-end> a range of marks
   * !<start-end> everything except the range of marks

   .. note:: When using the ``set table`` or ``set vrf`` commands the mark
      settings are ignored and overwritten with a table-specific mark that
      is set to 0x7FFFFFFF - the id of the table/VRF.

.. cfgcmd:: set policy route <name> rule <n> source address
   <match_criteria>
.. cfgcmd:: set policy route <name> rule <n> destination address
   <match_criteria>
.. cfgcmd:: set policy route6 <name> rule <n> source address
   <match_criteria>
.. cfgcmd:: set policy route6 <name> rule <n> destination address
   <match_criteria>

   Set match criteria based on source or destination ipv4|ipv6 address, where
   <match_criteria> could be:

For ipv4:
   * <x.x.x.x>: IP address to match.
   * <x.x.x.x/x>: Subnet to match.
   * <x.x.x.x>-<x.x.x.x>: IP range to match.
   * !<x.x.x.x>: Match everything except the specified address.
   * !<x.x.x.x/x>: Match everything except the specified subnet.
   * !<x.x.x.x>-<x.x.x.x>: Match everything except the specified range.

And for ipv6:
   * <h:h:h:h:h:h:h:h>: IPv6 address to match.
   * <h:h:h:h:h:h:h:h/x>: IPv6 prefix to match.
   * <h:h:h:h:h:h:h:h>-<h:h:h:h:h:h:h:h>: IPv6 range to match.
   * !<h:h:h:h:h:h:h:h>: Match everything except the specified address.
   * !<h:h:h:h:h:h:h:h/x>: Match everything except the specified prefix.
   * !<h:h:h:h:h:h:h:h>-<h:h:h:h:h:h:h:h>: Match everything except the
     specified range.

.. cfgcmd:: set policy route <name> rule <n> source group
   <address-group|domain-group|mac-group|network-group|port-group> <text>
.. cfgcmd:: set policy route <name> rule <n> destination group
   <address-group|domain-group|mac-group|network-group|port-group> <text>
.. cfgcmd:: set policy route6 <name> rule <n> source group
   <address-group|domain-group|mac-group|network-group|port-group> <text>
.. cfgcmd:: set policy route6 <name> rule <n> destination group
   <address-group|domain-group|mac-group|network-group|port-group> <text>

   Set match criteria based on source or destination groups, where <text>
   would be the group name/identifier. Prepend character '!' for inverted
   matching criteria.

.. cfgcmd:: set policy route <name> rule <n> destination port <match_criteria>
.. cfgcmd:: set policy route6 <name> rule <n> destination port <match_criteria>

   Set match criteria based on destination port, where <match_criteria> could
   be:

   * <port name>: Named port (any name in /etc/services, e.g., http).
   * <1-65535>: Numbered port.
   * <start>-<end>: Numbered port range (e.g., 1001-1005).

   Multiple destination ports can be specified as a comma-separated list. The
   whole list can also be "negated" using '!'. For example:
   '!22,telnet,http,123,1001-1005'

.. cfgcmd:: set policy route <name> rule <n> disable
.. cfgcmd:: set policy route6 <name> rule <n> disable

   Option to disable rule.

.. cfgcmd:: set policy route <name> rule <n> dscp <text>
.. cfgcmd:: set policy route6 <name> rule <n> dscp <text>
.. cfgcmd:: set policy route <name> rule <n> dscp-exclude <text>
.. cfgcmd:: set policy route6 <name> rule <n> dscp-exclude <text>

   Match based on dscp value criteria. Multiple values from 0 to 63
   and ranges are supported.

.. cfgcmd:: set policy route <name> rule <n> fragment
   <match-grag|match-non-frag>
.. cfgcmd:: set policy route6 <name> rule <n> fragment
   <match-grag|match-non-frag>

   Set IP fragment match, where:

   * match-frag: Second and further fragments of fragmented packets.
   * match-non-frag: Head fragments or unfragmented packets.

.. cfgcmd:: set policy route <name> rule <n> icmp <code | type>
.. cfgcmd:: set policy route6 <name> rule <n> icmpv6 <code | type>

   Match based on icmp|icmpv6 code and type.

.. cfgcmd:: set policy route <name> rule <n> icmp type-name <text>
.. cfgcmd:: set policy route6 <name> rule <n> icmpv6 type-name <text>

   Match based on icmp|icmpv6 type-name criteria. Use tab for information
   about what type-name criteria are supported.

.. cfgcmd:: set policy route <name> rule <n> ipsec
   <match-ipsec|match-none>
.. cfgcmd:: set policy route6 <name> rule <n> ipsec
   <match-ipsec|match-none>

   Set IPSec inbound match criterias, where:

   * match-ipsec: match inbound IPsec packets.
   * match-none: match inbound non-IPsec packets.

.. cfgcmd:: set policy route <name> rule <n> limit burst <0-4294967295>
.. cfgcmd:: set policy route6 <name> rule <n> limit burst <0-4294967295>

   Set maximum number of packets to alow in excess of rate.

.. cfgcmd:: set policy route <name> rule <n> limit rate <text>
.. cfgcmd:: set policy route6 <name> rule <n> limit rate <text>

   Set maximum average matching rate. Format for rate: integer/time_unit, where
   time_unit could be any one of second, minute, hour or day.For example
   1/second implies rule to be matched at an average of once per second.

.. cfgcmd:: set policy route <name> rule <n> protocol
   <text | 0-255 | tcp_udp | all >
.. cfgcmd:: set policy route6 <name> rule <n> protocol
   <text | 0-255 | tcp_udp | all >

   Match a protocol criteria. A protocol number or a name which is defined in:
   ``/etc/protocols``. Special names are ``all`` for all protocols and
   ``tcp_udp`` for tcp and udp based packets. The ``!`` negates the selected
   protocol.

.. cfgcmd:: set policy route <name> rule <n> packet-length <text>
.. cfgcmd:: set policy route6 <name> rule <n> packet-length <text>
.. cfgcmd:: set policy route <name> rule <n> packet-length-exclude <text>
.. cfgcmd:: set policy route6 <name> rule <n> packet-length-exclude <text>

   Match based on packet length criteria. Multiple values from 1 to 65535
   and ranges are supported.

.. cfgcmd:: set policy route <name> rule <n> packet-type [broadcast | host
   | multicast | other]
.. cfgcmd:: set policy route6 <name> rule <n> packet-type [broadcast | host
   | multicast | other]

   Match based on packet type criteria.

.. cfgcmd:: set policy route <name> rule <n> recent count <1-255>
.. cfgcmd:: set policy route6 <name> rule <n> recent count <1-255>
.. cfgcmd:: set policy route <name> rule <n> recent time <1-4294967295>
.. cfgcmd:: set policy route6 <name> rule <n> recent time <1-4294967295>

   Set parameters for matching recently seen sources. This match could be used
   by seeting count (source address seen more than <1-255> times) and/or time
   (source address seen in the last <0-4294967295> seconds).

.. cfgcmd:: set policy route <name> rule <n> state
   <established | invalid | new | related>
.. cfgcmd:: set policy route6 <name> rule <n> state
   <established | invalid | new | related>

   Set match criteria based on session state.

.. cfgcmd:: set policy route <name> rule <n> tcp flags <text>
.. cfgcmd:: set policy route6 <name> rule <n> tcp flags <text>

   Set match criteria based on tcp flags. Allowed values for TCP flags: SYN ACK
   FIN RST URG PSH ALL. When specifying more than one flag, flags should be
   comma-separated. For example : value of 'SYN,!ACK,!FIN,!RST' will only match
   packets with the SYN flag set, and the ACK, FIN and RST flags unset.

.. cfgcmd:: set policy route <name> rule <n> time monthdays <text>
.. cfgcmd:: set policy route6 <name> rule <n> time monthdays <text>
.. cfgcmd:: set policy route <name> rule <n> time startdate <text>
.. cfgcmd:: set policy route6 <name> rule <n> time startdate <text>
.. cfgcmd:: set policy route <name> rule <n> time starttime <text>
.. cfgcmd:: set policy route6 <name> rule <n> time starttime <text>
.. cfgcmd:: set policy route <name> rule <n> time stopdate <text>
.. cfgcmd:: set policy route6 <name> rule <n> time stopdate <text>
.. cfgcmd:: set policy route <name> rule <n> time stoptime <text>
.. cfgcmd:: set policy route6 <name> rule <n> time stoptime <text>
.. cfgcmd:: set policy route <name> rule <n> time weekdays <text>
.. cfgcmd:: set policy route6 <name> rule <n> time weekdays <text>
.. cfgcmd:: set policy route <name> rule <n> time utc
.. cfgcmd:: set policy route6 <name> rule <n> time utc

   Time to match the defined rule.

.. cfgcmd:: set policy route rule <n> ttl <eq | gt | lt> <0-255>

   Match time to live parameter, where 'eq' stands for 'equal'; 'gt' stands for
   'greater than', and 'lt' stands for 'less than'.

.. cfgcmd:: set policy route6 rule <n> hop-limit <eq | gt | lt> <0-255>

   Match hop-limit parameter, where 'eq' stands for 'equal'; 'gt' stands for
   'greater than', and 'lt' stands for 'less than'.

Actions
=======

When mathcing all patterns defined in a rule, then different actions can
be made. This includes droping the packet, modifying certain data, or
setting a different routing table.

.. cfgcmd:: set policy route <name> rule <n> action drop
.. cfgcmd:: set policy route6 <name> rule <n> action drop

   Set rule action to drop.

.. cfgcmd:: set policy route <name> rule <n> set connection-mark
   <1-2147483647>
.. cfgcmd:: set policy route6 <name> rule <n> set connection-mark
   <1-2147483647>

   Set a specific connection mark.

.. cfgcmd:: set policy route <name> rule <n> set dscp <0-63>
.. cfgcmd:: set policy route6 <name> rule <n> set dscp <0-63>

   Set packet modifications: Packet Differentiated Services Codepoint (DSCP)

.. cfgcmd:: set policy route <name> rule <n> set mark <1-2147483647>
.. cfgcmd:: set policy route6 <name> rule <n> set mark <1-2147483647>

   Set a specific packet mark.

.. cfgcmd:: set policy route <name> rule <n> set table <main | 1-200>
.. cfgcmd:: set policy route6 <name> rule <n> set table <main | 1-200>

   Set the routing table to forward packet with.

   .. note:: When using the ``set table`` or ``set vrf`` commands matching
      against the mark is not possible, because it gets overwritten with a
      table-specific mark that is 0x7FFFFFFF - the id of the table/VRF.

.. cfgcmd:: set policy route <name> rule <n> set tcp-mss <500-1460>
.. cfgcmd:: set policy route6 <name> rule <n> set tcp-mss <500-1460>

   Set packet modifications: Explicitly set TCP Maximum segment size value.

.. cfgcmd:: set policy route <name> rule <n> set vrf <default | text >
.. cfgcmd:: set policy route6 <name> rule <n> set vrf <default | text >

   Set the VRF to forward packet with.

   .. note:: When using the ``set table`` or ``set vrf`` commands matching
      against the mark is not possible, because it gets overwritten with a
      table-specific mark that is 0x7FFFFFFF - the id of the table/VRF.
