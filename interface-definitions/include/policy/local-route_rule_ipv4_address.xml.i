<!-- include start from policy/local-route_rule_ipv4_address.xml.i -->
<leafNode name="address">
  <properties>
    <help>IPv4 address or prefix</help>
    <valueHelp>
      <format>ipv4</format>
      <description>Address to match against</description>
    </valueHelp>
    <valueHelp>
      <format>ipv4net</format>
      <description>Prefix to match against</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
      <validator name="ip-prefix"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
