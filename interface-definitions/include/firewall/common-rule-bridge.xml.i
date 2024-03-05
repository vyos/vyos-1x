<!-- include start from firewall/common-rule-bridge.xml.i -->
#include <include/firewall/action-l2.xml.i>
#include <include/firewall/nft-queue.xml.i>
<node name="destination">
  <properties>
    <help>Destination parameters</help>
  </properties>
  <children>
    #include <include/firewall/mac-address.xml.i>
  </children>
</node>
#include <include/generic-disable-node.xml.i>
<leafNode name="jump-target">
  <properties>
    <help>Set jump target. Action jump must be defined to use this setting</help>
    <completionHelp>
      <path>firewall bridge name</path>
    </completionHelp>
  </properties>
</leafNode>
#include <include/firewall/log.xml.i>
#include <include/firewall/log-options.xml.i>
<node name="source">
  <properties>
    <help>Source parameters</help>
  </properties>
  <children>
    #include <include/firewall/mac-address.xml.i>
  </children>
</node>
#include <include/firewall/inbound-interface.xml.i>
#include <include/firewall/outbound-interface.xml.i>
#include <include/firewall/match-vlan.xml.i>
<!-- include end -->
