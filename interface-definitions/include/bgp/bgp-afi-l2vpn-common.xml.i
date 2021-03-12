<!-- included start from bgp-afi-l2vpn-common.xml.i -->
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
<leafNode name="rd">
  <properties>
    <help>Route Distinguisher</help>
    <valueHelp>
      <format>txt</format>
      <description>Route Distinguisher, (x.x.x.x:yyy|xxxx:yyyy)</description>
    </valueHelp>
    <constraint>
      <regex>^((25[0-5]|2[0-4][0-9]|[1][0-9][0-9]|[1-9][0-9]|[0-9]?)(\.(25[0-5]|2[0-4][0-9]|[1][0-9][0-9]|[1-9][0-9]|[0-9]?)){3}|[0-9]{1,10}):[0-9]{1,5}$</regex>
    </constraint>
  </properties>
</leafNode>
#include <include/bgp/bgp-route-target.xml.i>
<!-- included end -->
