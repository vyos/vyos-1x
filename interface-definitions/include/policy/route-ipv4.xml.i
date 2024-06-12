<!-- include start from policy/route-ipv4.xml.i -->
<node name="source">
  <properties>
    <help>Source parameters</help>
  </properties>
  <children>
    #include <include/firewall/address.xml.i>
    #include <include/firewall/source-destination-group.xml.i>
    #include <include/firewall/mac-address.xml.i>
    #include <include/firewall/port.xml.i>
  </children>
</node>
#include <include/firewall/icmp.xml.i>
<!-- include end -->
