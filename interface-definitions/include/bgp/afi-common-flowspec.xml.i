<!-- included start from bgp-afi-common-flowspec.xml.i -->
<node name="filter-list">
  <properties>
    <help>as-path-list to filter route updates to/from this peer</help>
  </properties>
  <children>
    <leafNode name="export">
      <properties>
        <help>As-path-list to filter outgoing route updates to this peer</help>
        <completionHelp>
          <path>policy as-path-list</path>
        </completionHelp>
      </properties>
    </leafNode>
    <leafNode name="import">
      <properties>
        <help>As-path-list to filter incoming route updates from this peer</help>
        <completionHelp>
          <path>policy as-path-list</path>
        </completionHelp>
      </properties>
    </leafNode>
  </children>
</node>
#include <include/bgp/afi-route-map.xml.i>
#include <include/bgp/afi-route-reflector-client.xml.i>
#include <include/bgp/afi-route-server-client.xml.i>
#include <include/bgp/afi-soft-reconfiguration.xml.i>
<!-- included end -->
