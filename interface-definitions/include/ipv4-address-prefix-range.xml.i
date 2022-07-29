<!-- include start from ipv4-address-prefix-range.xml.i -->
<leafNode name="address">
  <properties>
    <help>IP address, subnet, or range</help>
    <valueHelp>
      <format>ipv4</format>
      <description>IPv4 address to match</description>
    </valueHelp>
    <valueHelp>
      <format>ipv4net</format>
      <description>IPv4 prefix to match</description>
    </valueHelp>
    <valueHelp>
      <format>ipv4range</format>
      <description>IPv4 address range to match</description>
    </valueHelp>
    <valueHelp>
      <format>!ipv4</format>
      <description>Match everything except the specified address</description>
    </valueHelp>
    <valueHelp>
      <format>!ipv4net</format>
      <description>Match everything except the specified prefix</description>
    </valueHelp>
    <valueHelp>
      <format>!ipv4range</format>
      <description>Match everything except the specified range</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
      <validator name="ipv4-prefix"/>
      <validator name="ipv4-range"/>
      <validator name="ipv4-address-exclude"/>
      <validator name="ipv4-prefix-exclude"/>
      <validator name="ipv4-range-exclude"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
