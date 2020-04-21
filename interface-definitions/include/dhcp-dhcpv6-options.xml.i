<node name="dhcp-options">
  <properties>
    <help>DHCP options</help>
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
<node name="dhcpv6-options">
  <properties>
    <help>DHCPv6 options</help>
  </properties>
  <children>
    <leafNode name="parameters-only">
      <properties>
        <help>Acquire only config parameters, no address</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="temporary">
      <properties>
        <help>IPv6 "temporary" address</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
