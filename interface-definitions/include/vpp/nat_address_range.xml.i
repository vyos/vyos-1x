<!-- include start from vpp/nat_address_range.xml.i -->
<leafNode name="address">
  <properties>
    <help>IP address or range</help>
    <valueHelp>
      <format>ipv4</format>
      <description>IPv4 address</description>
    </valueHelp>
    <valueHelp>
      <format>ipv4range</format>
      <description>IPv4 address range</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
      <validator name="ipv4-range"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
