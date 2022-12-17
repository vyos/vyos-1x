<!-- include start from firewall/mac-address.xml.i -->
<leafNode name="mac-address">
  <properties>
    <help>MAC address</help>
    <valueHelp>
      <format>macaddr</format>
      <description>MAC address to match</description>
    </valueHelp>
    <valueHelp>
      <format>!macaddr</format>
      <description>Match everything except the specified MAC address</description>
    </valueHelp>
    <constraint>
      <validator name="mac-address"/>
      <validator name="mac-address-exclude"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
