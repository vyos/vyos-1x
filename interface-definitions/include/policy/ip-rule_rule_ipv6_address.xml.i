<!-- include start from policy/local-route_rule_ipv6_address.xml.i -->
<leafNode name="address">
  <properties>
    <help>IPv6 address or prefix</help>
    <valueHelp>
      <format>ipv6</format>
      <description>Address to match against</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6net</format>
      <description>Prefix to match against</description>
    </valueHelp>
    <constraint>
      <validator name="ipv6-address"/>
      <validator name="ipv6-prefix"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
