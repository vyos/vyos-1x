<leafNode name="address">
  <properties>
    <help>IP address</help>
    <valueHelp>
      <format>ipv4net</format>
      <description>IPv4 address and prefix length</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6net</format>
      <description>IPv6 address and prefix length</description>
    </valueHelp>
    <constraint>
      <validator name="ip-cidr"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
