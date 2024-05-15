<!-- include start from firewall/common-rule-ipv4.xml.i -->
#include <include/firewall/add-addr-to-group-ipv4.xml.i>
#include <include/firewall/common-rule-inet.xml.i>
#include <include/firewall/icmp.xml.i>
#include <include/firewall/ttl.xml.i>
<node name="destination">
  <properties>
    <help>Destination parameters</help>
  </properties>
  <children>
    #include <include/firewall/address.xml.i>
    #include <include/firewall/address-mask.xml.i>
    #include <include/firewall/fqdn.xml.i>
    #include <include/firewall/geoip.xml.i>
    #include <include/firewall/mac-address.xml.i>
    #include <include/firewall/port.xml.i>
    #include <include/firewall/source-destination-group.xml.i>
    #include <include/firewall/source-destination-dynamic-group.xml.i>
  </children>
</node>
<leafNode name="jump-target">
  <properties>
    <help>Set jump target. Action jump must be defined to use this setting</help>
    <completionHelp>
      <path>firewall ipv4 name</path>
    </completionHelp>
  </properties>
</leafNode>
<node name="source">
  <properties>
    <help>Source parameters</help>
  </properties>
  <children>
    #include <include/firewall/address.xml.i>
    #include <include/firewall/address-mask.xml.i>
    #include <include/firewall/fqdn.xml.i>
    #include <include/firewall/geoip.xml.i>
    #include <include/firewall/mac-address.xml.i>
    #include <include/firewall/port.xml.i>
    #include <include/firewall/source-destination-group.xml.i>
    #include <include/firewall/source-destination-dynamic-group.xml.i>
  </children>
</node>
<!-- include end -->