<leafNode name="source-address">
  <properties>
    <help>IPv4/IPv6 source address</help>
    <valueHelp>
      <format>ipv4</format>
      <description>IPv4 source-address</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6</format>
      <description>IPv6 source-address</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
      <validator name="ipv6-address"/>
    </constraint>
  </properties>
</leafNode>
