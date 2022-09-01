<!-- include start from ipv4-address-prefix.xml.i -->
<leafNode name="address">
  <properties>
    <help>IP address, prefix</help>
    <valueHelp>
      <format>ipv4</format>
      <description>IPv4 address to match</description>
    </valueHelp>
    <valueHelp>
      <format>ipv4net</format>
      <description>IPv4 prefix to match</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
      <validator name="ipv4-prefix"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
