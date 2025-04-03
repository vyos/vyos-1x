<!-- include start from bgp/afi-route-map-vrf.xml.i -->
<node name="route-map">
  <properties>
    <help>Route-map to filter route updates to/from this peer</help>
  </properties>
  <children>
    <node name="vrf">
      <properties>
        <help>Between current address-family and VRF</help>
      </properties>
      <children>
        #include <include/bgp/afi-route-map-import.xml.i>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
