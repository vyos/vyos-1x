<!-- include start from firewall/address-ipv6.xml.i -->
<leafNode name="address">
  <properties>
    <help>IP address, subnet, or range</help>
    <valueHelp>
      <format>ipv6</format>
      <description>IP address to match</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6net</format>
      <description>Subnet to match</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6range</format>
      <description>IP range to match</description>
    </valueHelp>
    <valueHelp>
      <format>!ipv6</format>
      <description>Match everything except the specified address</description>
    </valueHelp>
    <valueHelp>
      <format>!ipv6net</format>
      <description>Match everything except the specified prefix</description>
    </valueHelp>
    <valueHelp>
      <format>!ipv6range</format>
      <description>Match everything except the specified range</description>
    </valueHelp>
    <constraint>
      <validator name="ipv6"/>
      <validator name="ipv6-exclude"/>
      <validator name="ipv6-range"/>
      <validator name="ipv6-range-exclude"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
