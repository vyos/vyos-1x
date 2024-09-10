<!-- include start from firewall/common-rule-bridge.xml.i -->
#include <include/generic-description.xml.i>
#include <include/generic-disable-node.xml.i>
#include <include/firewall/dscp.xml.i>
#include <include/firewall/firewall-mark.xml.i>
#include <include/firewall/fragment.xml.i>
#include <include/firewall/hop-limit.xml.i>
#include <include/firewall/icmp.xml.i>
#include <include/firewall/icmpv6.xml.i>
#include <include/firewall/limit.xml.i>
#include <include/firewall/log.xml.i>
#include <include/firewall/log-options.xml.i>
#include <include/firewall/match-ether-type.xml.i>
#include <include/firewall/match-ipsec.xml.i>
#include <include/firewall/match-vlan.xml.i>
#include <include/firewall/nft-queue.xml.i>
#include <include/firewall/packet-options.xml.i>
#include <include/firewall/protocol.xml.i>
#include <include/firewall/tcp-flags.xml.i>
#include <include/firewall/tcp-mss.xml.i>
#include <include/firewall/time.xml.i>
#include <include/firewall/ttl.xml.i>
<node name="destination">
  <properties>
    <help>Destination parameters</help>
  </properties>
  <children>
    #include <include/firewall/mac-address.xml.i>
    #include <include/firewall/address-inet.xml.i>
    #include <include/firewall/address-mask-inet.xml.i>
    #include <include/firewall/port.xml.i>
    #include <include/firewall/source-destination-group-inet.xml.i>
  </children>
</node>
<leafNode name="jump-target">
  <properties>
    <help>Set jump target. Action jump must be defined to use this setting</help>
    <completionHelp>
      <path>firewall bridge name</path>
    </completionHelp>
  </properties>
</leafNode>
<node name="source">
  <properties>
    <help>Source parameters</help>
  </properties>
  <children>
    #include <include/firewall/mac-address.xml.i>
    #include <include/firewall/address-inet.xml.i>
    #include <include/firewall/address-mask-inet.xml.i>
    #include <include/firewall/port.xml.i>
    #include <include/firewall/source-destination-group-inet.xml.i>
  </children>
</node>
<!-- include end -->
