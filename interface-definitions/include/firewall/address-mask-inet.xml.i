<!-- include start from firewall/address-mask-inet.xml.i -->
<leafNode name="address-mask">
  <properties>
    <help>IP mask</help>
    <valueHelp>
      <format>ipv4</format>
      <description>IPv4 mask to apply</description>
    </valueHelp>
     <valueHelp>
      <format>ipv6</format>
      <description>IP mask to apply</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
      <validator name="ipv6"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->