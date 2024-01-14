<!-- include start from bgp/afi-nexthop-vpn-export.xml.i -->
<node name="nexthop">
  <properties>
    <help>Specify next hop to use for VRF advertised prefixes</help>
  </properties>
  <children>
    <node name="vpn">
      <properties>
        <help>Between current address-family and vpn</help>
      </properties>
      <children>
        <leafNode name="export">
          <properties>
            <help>For routes leaked from current address-family to vpn</help>
            <valueHelp>
                <format>ipv4</format>
                <description>BGP neighbor IP address</description>
              </valueHelp>
              <valueHelp>
                <format>ipv6</format>
                <description>BGP neighbor IPv6 address</description>
              </valueHelp>
              <constraint>
                <validator name="ip-address"/>
              </constraint>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</node>
  <!-- include end -->
