<!-- include start from bgp/afi-l2vpn-common.xml.i -->
<leafNode name="advertise-default-gw">
  <properties>
    <help>Advertise All default g/w mac-ip routes in EVPN</help>
    <valueless/>
  </properties>
</leafNode>
<leafNode name="advertise-svi-ip">
  <properties>
    <help>Advertise svi mac-ip routes in EVPN</help>
    <valueless/>
  </properties>
</leafNode>
#include <include/bgp/route-distinguisher.xml.i>
<node name="route-target">
  <properties>
    <help>Route Target</help>
  </properties>
  <children>
    #include <include/bgp/route-target-both.xml.i>
    #include <include/bgp/route-target-export.xml.i>
    #include <include/bgp/route-target-import.xml.i>
  </children>
</node>
<!-- include end -->
