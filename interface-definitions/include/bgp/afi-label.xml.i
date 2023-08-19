<!-- include start from bgp/afi-label.xml.i -->
<node name="label">
  <properties>
    <help>Label value for VRF</help>
  </properties>
  <children>
    <node name="vpn">
      <properties>
        <help>Between current address-family and VPN</help>
      </properties>
      <children>
        <leafNode name="export">
          <properties>
            <help>For routes leaked from current address-family to VPN</help>
            <completionHelp>
              <list>auto</list>
            </completionHelp>
            <valueHelp>
              <format>auto</format>
              <description>Automatically assign a label</description>
            </valueHelp>
            <valueHelp>
              <format>u32:0-1048575</format>
              <description>Label Value</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 0-1048575"/>
              <regex>(auto)</regex>
            </constraint>
          </properties>
        </leafNode>
        <node name="allocation-mode">
          <properties>
            <help>Label allocation mode</help>
          </properties>
          <children>
            <leafNode name="per-nexthop">
              <properties>
                <help>Allocate a label per connected next-hop in the VRF</help>
                <valueless/>
              </properties>
            </leafNode>
          </children>
        </node>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
