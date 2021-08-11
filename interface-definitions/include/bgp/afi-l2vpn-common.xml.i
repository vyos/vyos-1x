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
#include <include/bgp/route-target.xml.i>
<!-- include end -->
