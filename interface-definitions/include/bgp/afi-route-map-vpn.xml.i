<!-- include start from bgp/afi-route-map-vpn.xml.i -->
<node name="route-map">
  <properties>
    <help>Route-map to filter route updates to/from this peer</help>
  </properties>
  <children>
    <node name="vpn">
      <properties>
        <help>Between current address-family and VPN</help>
      </properties>
      <children>
        #include <include/bgp/afi-route-map-export-import.xml.i>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
