<!-- include start from bgp/afi-aggregate-address.xml.i -->
<leafNode name="as-set">
  <properties>
    <help>Generate AS-set path information for this aggregate address</help>
    <valueless/>
  </properties>
</leafNode>
#include <include/route-map.xml.i>
<leafNode name="summary-only">
  <properties>
    <help>Announce the aggregate summary network only</help>
    <valueless/>
  </properties>
</leafNode>
<!-- include end -->
