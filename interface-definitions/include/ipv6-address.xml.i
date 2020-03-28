<node name="address">
  <children>
    <leafNode name="autoconf">
      <properties>
        <help>Enable acquisition of IPv6 address using stateless autoconfig (SLAAC)</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="eui64">
      <properties>
        <help>ssign IPv6 address using EUI-64 based on MAC address</help>
        <valueHelp>
          <format>ipv6net</format>
          <description>IPv6 address and prefix length</description>
        </valueHelp>
        <constraint>
          <validator name="ipv6-prefix"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
