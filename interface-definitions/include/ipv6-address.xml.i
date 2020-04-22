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
        <help>Prefix for IPv6 address with MAC-based EUI-64</help>
        <valueHelp>
          <format>ipv6net</format>
          <description>IPv6 network and prefix length</description>
        </valueHelp>
        <constraint>
          <validator name="ipv6-prefix"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
  </children>
</node>
