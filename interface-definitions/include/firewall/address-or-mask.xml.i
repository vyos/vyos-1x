<!-- include start from firewall/address.xml.i -->
<leafNode name="address">
  <properties>
    <help>IP address or subnet</help>
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
