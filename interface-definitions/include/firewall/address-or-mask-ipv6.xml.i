<!-- include start from firewall/address-or-mask-ipv6.xml.i -->
<leafNode name="address">
  <properties>
    <help>IP address or Subnet</help>
    <valueHelp>
      <format>ipv6</format>
      <description>IP address to match</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6net</format>
      <description>Subnet to match</description>
    </valueHelp>
    <constraint>
      <validator name="ipv6-address"/>
      <validator name="ipv6-prefix"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
