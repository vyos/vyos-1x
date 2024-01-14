<!-- include start from bgp/sid.xml.i -->
<node name="sid">
    <properties>
      <help>SID value for VRF</help>
    </properties>
    <children>
      <node name="vpn">
        <properties>
          <help>Between current VRF and VPN</help>
        </properties>
        <children>
          <leafNode name="export">
            <properties>
              <help>For routes leaked from current VRF to VPN</help>
              <completionHelp>
                <list>auto</list>
              </completionHelp>
              <valueHelp>
                <format>u32:1-1048575</format>
                <description>SID allocation index</description>
              </valueHelp>
              <valueHelp>
                <format>auto</format>
                <description>Automatically assign a label</description>
              </valueHelp>
              <constraint>
                <regex>auto</regex>
                <validator name="numeric" argument="--range 1-1048575"/>
              </constraint>
            </properties>
          </leafNode>
        </children>
      </node>
    </children>
  </node>
  <!-- include end -->
