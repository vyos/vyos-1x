<!-- included start from dhcp-options.xml.i -->
<node name="dhcp-options">
  <properties>
    <help>DHCP client settings/options</help>
  </properties>
  <children>
    <leafNode name="client-id">
      <properties>
        <help>DHCP client identifier</help>
      </properties>
    </leafNode>
    <leafNode name="host-name">
      <properties>
        <help>DHCP client host name (overrides system host name)</help>
      </properties>
    </leafNode>
    <leafNode name="vendor-class-id">
      <properties>
        <help>DHCP client vendor type</help>
      </properties>
    </leafNode>
  </children>
</node>
<!-- included end -->
