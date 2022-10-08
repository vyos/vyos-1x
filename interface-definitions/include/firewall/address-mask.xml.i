<!-- include start from firewall/address-mask.xml.i -->
<leafNode name="address-mask">
  <properties>
    <help>IP mask</help>
    <valueHelp>
      <format>ipv4</format>
      <description>IPv4 mask to apply</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
