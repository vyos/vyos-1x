<!-- include start from bgp/afi-export-import.xml.i -->
<node name="export">
  <properties>
    <help>Export routes from this address-family</help>
  </properties>
  <children>
    <leafNode name="vpn">
      <properties>
        <help>to/from default instance VPN RIB</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<node name="import">
  <properties>
    <help>Import routes to this address-family</help>
  </properties>
  <children>
    <leafNode name="vpn">
      <properties>
        <help>to/from default instance VPN RIB</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="vrf">
      <properties>
        <help>VRF to import from</help>
        <valueHelp>
          <format>txt</format>
          <description>VRF instance name</description>
        </valueHelp>
        <completionHelp>
          <path>vrf name</path>
          <list>default</list>
        </completionHelp>
        <multi/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
