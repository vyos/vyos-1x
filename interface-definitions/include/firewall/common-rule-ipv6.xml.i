<!-- include start from firewall/common-rule-ipv6.xml.i -->
#include <include/firewall/add-addr-to-group-ipv6.xml.i>
#include <include/firewall/common-rule-inet.xml.i>
#include <include/firewall/hop-limit.xml.i>
#include <include/firewall/icmpv6.xml.i>
<node name="destination">
  <properties>
    <help>Destination parameters</help>
  </properties>
  <children>
    #include <include/firewall/address-ipv6.xml.i>
    #include <include/firewall/address-mask-ipv6.xml.i>
    #include <include/firewall/fqdn.xml.i>
    #include <include/firewall/geoip.xml.i>
    #include <include/firewall/mac-address.xml.i>
    #include <include/firewall/port.xml.i>
    #include <include/firewall/source-destination-group-ipv6.xml.i>
    #include <include/firewall/source-destination-dynamic-group-ipv6.xml.i>
  </children>
</node>
<leafNode name="jump-target">
  <properties>
    <help>Set jump target. Action jump must be defined to use this setting</help>
    <completionHelp>
      <path>firewall ipv6 name</path>
    </completionHelp>
  </properties>
</leafNode>
<node name="source">
  <properties>
    <help>Source parameters</help>
  </properties>
  <children>
    #include <include/firewall/address-ipv6.xml.i>
    #include <include/firewall/address-mask-ipv6.xml.i>
    #include <include/firewall/fqdn.xml.i>
    #include <include/firewall/geoip.xml.i>
    #include <include/firewall/mac-address.xml.i>
    #include <include/firewall/port.xml.i>
    #include <include/firewall/source-destination-group-ipv6.xml.i>
    #include <include/firewall/source-destination-dynamic-group-ipv6.xml.i>
  </children>
</node>
<!-- include end -->