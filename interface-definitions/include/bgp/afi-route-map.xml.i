<!-- include start from bgp/afi-route-map.xml.i -->
<node name="route-map">
  <properties>
    <help>Route-map to filter route updates to/from this peer</help>
  </properties>
  <children>
    #include <include/bgp/afi-route-map-export-import.xml.i>
  </children>
</node>
<!-- include end -->
