<!-- include start from qos/class-match-ipv4-address.xml.i -->
<leafNode name="address">
  <properties>
    <help>IPv4 destination address for this match</help>
    <valueHelp>
      <format>ipv4</format>
      <description>IPv4 address</description>
    </valueHelp>
    <valueHelp>
      <format>ipv4net</format>
      <description>IPv4 prefix</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
      <validator name="ipv4-prefix"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
