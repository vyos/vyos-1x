<!-- include start from interface/address-ipv4-ipv6.xml.i -->
<leafNode name="address">
  <properties>
    <help>IP address</help>
    <valueHelp>
      <format>ipv4</format>
      <description>IPv4 address</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6</format>
      <description>IPv6 address</description>
    </valueHelp>
    <constraint>
      <validator name="ip-address"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
