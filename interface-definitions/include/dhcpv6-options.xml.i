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
